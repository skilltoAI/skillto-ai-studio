"""Isolated yt-dlp worker. No browser-profile discovery or credential export."""
import json
import os
from pathlib import Path
import sys
import contextlib
import shutil
import tempfile
import re
import subprocess
from urllib.parse import urlsplit, parse_qs
from dependencies import ffmpeg_path

def page_url(value):
    """Normalize a selected Douyin modal without touching signed media URLs."""
    parsed = urlsplit(value)
    if parsed.hostname in ('douyin.com', 'www.douyin.com'):
        query = parse_qs(parsed.query)
        video_id = next((query[key][0] for key in ('modal_id', 'vid')
                         if key in query and re.fullmatch(r'[0-9]+', query[key][0])), None)
        if video_id:
            return f'https://www.douyin.com/video/{video_id}'
    return value

def failure_message(error):
    """Return allowlisted explanations only; upstream text can contain secrets."""
    text = str(error).lower()
    if 'fresh cookies' in text:
        return '抖音页面解析未取得详情：yt-dlp 要求新鲜 Cookie（不一定需要登录）。本工具不会自动读取浏览器身份；可人工选择扫描到的媒体资源，或按采集子 skill 的授权流程处理会话'
    if any(word in text for word in ('captcha', 'challenge', 'verify you', 'sign in', 'login required', 'log in')):
        return '平台要求登录或人工验证，任务已停止；请按采集子 skill 的同会话人工流程处理'
    if '429' in text or 'too many requests' in text:
        return '平台限流，任务已停止；请稍后人工操作，不要自动重试或切换身份'
    if '403' in text or '401' in text:
        return '媒体请求被拒绝（401/403）：可能是访问权限、来源校验或链接过期；请回原页面人工检查，不自动重试'
    if 'unsupported url' in text:
        return '当前链接无法由 yt-dlp 解析；请打开单条视频详情页，或人工扫描并选择媒体资源'
    if 'ffmpeg' in text:
        return '媒体合并失败，请检查 FFmpeg 安装及音视频格式'
    if 'timed out' in text or 'timeout' in text:
        return '上游请求超时，任务已停止；请检查网络后人工重新提交'
    return '下载失败：链接过期、媒体不可用或平台暂不支持；请检查 yt-dlp / FFmpeg，勿自动重试绕过限制'

class Quiet:
    def debug(self, *a): pass
    def warning(self, *a): pass
    def error(self, *a): pass

def probe_media(file):
    """Read final container metadata with the existing FFmpeg, without decoding."""
    binary = ffmpeg_path()
    if not binary: return {}
    try:
        probe = subprocess.run([binary, '-hide_banner', '-i', str(file)],
            capture_output=True, text=True, errors='replace', timeout=15,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        metadata = {}
        video = next((line for line in probe.stderr.splitlines() if 'Video:' in line and 'attached pic' not in line), '')
        dimensions = re.search(r'\b([0-9]{2,5})x([0-9]{2,5})\b', video)
        if dimensions: metadata.update(width=int(dimensions[1]), height=int(dimensions[2]))
        duration = re.search(r'Duration: ([0-9]+):([0-9]+):([0-9.]+)', probe.stderr)
        if duration: metadata['duration'] = int(duration[1])*3600 + int(duration[2])*60 + float(duration[3])
        return metadata
    except (OSError, subprocess.TimeoutExpired): return {}

def run(args):
    import yt_dlp
    folder = Path(args['folder'])
    options = {'outtmpl': str(folder / 'video.%(ext)s'), 'noplaylist': True, 'quiet': True,
        'no_warnings': True, 'logger': Quiet(), 'retries': 0, 'fragment_retries': 0,
        'socket_timeout': 30, 'max_filesize': 2 * 1024**3, 'overwrites': False, 'skip_unavailable_fragments': False,
        'format': 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b', 'merge_output_format': 'mp4',
        'restrictfilenames': True, 'writethumbnail': False, 'writeinfojson': False,
        'allow_unplayable_formats': False, 'http_headers': {'Referer': args['source']},
        'match_filter': lambda info, *, incomplete=False: '暂不支持直播，请选择点播视频' if info.get('is_live') else None}
    ffmpeg = ffmpeg_path()
    if ffmpeg: options['ffmpeg_location'] = ffmpeg
    runtime = next((name for name in ('deno', 'node') if shutil.which(name)), None)
    if runtime: options['js_runtimes'] = {runtime: {}}
    # Session use is opt-in through one explicitly configured file, never Chrome profile extraction.
    cookie = os.environ.get('SKILLTO_WORKBENCH_COOKIE_FILE')
    with tempfile.TemporaryDirectory(prefix='skillto-session-') as session:
        if cookie:
            if 'xiaoyu' in str(cookie).lower(): raise ValueError('受限账号须使用采集子 skill 的逐任务授权流程')
            temporary = Path(session) / 'cookies.txt'
            shutil.copyfile(Path(cookie).resolve(strict=True), temporary)
            if os.name != 'nt': temporary.chmod(0o600)
            options['cookiefile'] = str(temporary)
        with contextlib.redirect_stdout(sys.stderr), yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(page_url(args['url']), download=True)
    files = [p for p in folder.iterdir() if p.suffix.lower() in ('.mp4', '.webm', '.mkv') and p.name.startswith('video.')]
    if len(files) != 1 or not files[0].stat().st_size: raise ValueError('视频未合并完成，请检查 FFmpeg')
    return {'ok': True, 'file': files[0].name, 'title': info.get('title'), 'duration': info.get('duration'), **probe_media(files[0])}

if __name__ == '__main__':
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        result = run(json.load(sys.stdin))
    except ImportError:
        result = {'ok': False, 'error': '缺少 yt-dlp，请运行安装检查'}
    except Exception as error:
        result = {'ok': False, 'error': failure_message(error)}
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result['ok'] else 1)
