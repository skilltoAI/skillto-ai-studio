"""Versioned, atomic demo derivatives; never rewrites a source URL or .motion package."""
import hashlib
import json
import os
import shutil
import subprocess
import threading
from pathlib import Path
from urllib.request import Request, build_opener
from urllib.error import HTTPError
import motion_store as store
from motion_network import download, check_url, Redirects

LIMIT = 512 * 1024 * 1024
THRESHOLD = 40_000_000  # decimal MB, strictly greater than 40 MB
POLICY = 'hevc720-v1'
LOCK = threading.RLock()
MEDIA_LOCKS = {}


def paths(url):
    key = hashlib.sha256(check_url(url).encode()).hexdigest()
    base = store.root() / 'media' / key
    return base.with_suffix('.mp4'), base.with_name(key+'-'+POLICY).with_suffix('.mp4')


def source_size(url):
    check_url(url)
    try:
        with build_opener(Redirects()).open(Request(url, method='HEAD', headers={'User-Agent':'SkilltoStudio/1.0'}), timeout=20) as r:
            value = r.headers.get('Content-Length')
            return int(value) if value else None
    except HTTPError as exc:
        if exc.code not in (405,501): raise
        return None


def probe(path, env):
    tool = shutil.which('ffprobe', path=env['PATH'])
    if not tool: raise ValueError('缺少 ffprobe，无法校验预览视频')
    result = subprocess.run([tool,'-v','error','-show_streams','-show_format','-of','json',str(path)], capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, timeout=30,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    if result.returncode: raise ValueError('预览视频探测失败：'+result.stderr[-1000:])
    return json.loads(result.stdout)


def scale_filter(width, height):
    # Fit a landscape/portrait 720p box; even dimensions, no upscaling or cropping.
    w,h = (1280,720) if width >= height else (720,1280)
    return f"scale=w='min(iw,{w})':h='min(ih,{h})':force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1"


def ensure_preview(url, env, execute=None, cancel=lambda:False, inspect_only=False):
    raw, derived = paths(url)
    with LOCK:
        lock=MEDIA_LOCKS.setdefault(str(derived),threading.RLock())
    with lock:
        if cancel(): raise InterruptedError('已取消')
        if derived.is_file() and derived.with_suffix('.json').is_file():
            if raw.is_file() and raw.stat().st_size > THRESHOLD: raw.unlink()
            raw.with_suffix('.source.mp4').unlink(missing_ok=True)
            return derived
        if not raw.is_file():
            if inspect_only:
                size=source_size(url)
                if size is not None and size <= THRESHOLD: return None
                if size is not None and size > LIMIT: raise ValueError('示例视频超过 512 MiB 下载上限')
            staged=raw.with_suffix('.source.mp4')
            try: download(url, staged, LIMIT, cancel)
            except BaseException:
                staged.unlink(missing_ok=True)
                raise
            if staged.stat().st_size <= THRESHOLD:
                staged.replace(raw)
                return raw
            raw=staged
        if raw.stat().st_size <= THRESHOLD: return raw
        try:
            tool=shutil.which('ffmpeg',path=env['PATH'])
            if not tool: raise ValueError('示例视频超过 40 MB，需要 ffmpeg H.265 转码')
            original=probe(raw,env)
            video=next((s for s in original['streams'] if s['codec_type']=='video'),None)
            if not video: raise ValueError('示例文件没有视频轨道')
            temporary=derived.with_suffix('.part.mp4')
            encoder=env.get('SKILLTO_MOTION_PREVIEW_ENCODER','libx265')
            if encoder not in ('libx265','hevc_nvenc'): raise ValueError('未支持的 H.265 预览编码器')
            encoding=(['-c:v','hevc_nvenc','-preset','p5','-rc','vbr','-cq','26','-b:v','0'] if encoder=='hevc_nvenc' else
                      ['-c:v','libx265','-preset','fast','-crf','26','-threads','4','-x265-params','pools=4:frame-threads=2'])
            args=[tool,'-hide_banner','-loglevel','error','-y','-i',str(raw),'-map','0:v:0','-map','0:a:0?',
                  '-vf',scale_filter(video['width'],video['height'])]+encoding+['-pix_fmt','yuv420p','-tag:v','hvc1',
                  '-c:a','aac','-b:a','128k','-movflags','+faststart',str(temporary)]
            if execute: execute(args)
            else:
                result=subprocess.run(args,capture_output=True,env=env,timeout=3600,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                if result.returncode: raise ValueError('H.265 转码失败：'+result.stderr.decode('utf-8','replace')[-1000:])
            if cancel(): raise InterruptedError('已取消')
            converted=probe(temporary,env)
            out=next(s for s in converted['streams'] if s['codec_type']=='video')
            maxw,maxh=(1280,720) if video['width']>=video['height'] else (720,1280)
            if out['codec_name']!='hevc' or out['width']>min(video['width'],maxw) or out['height']>min(video['height'],maxh):
                raise ValueError('预览编码或 720p 尺寸校验失败')
            duration=float(original['format']['duration']);after=float(converted['format']['duration'])
            if abs(duration-after)>max(.5,duration*.01): raise ValueError('转码后时长校验失败')
            if any(s['codec_type']=='audio' for s in original['streams']) and not any(s['codec_type']=='audio' for s in converted['streams']):
                raise ValueError('转码后音轨丢失')
            temporary.replace(derived)
            meta={'policy':POLICY,'sourceUrl':url,'originalBytes':raw.stat().st_size,'bytes':derived.stat().st_size,
                  'codec':'hevc','encoder':encoder,'tag':'hvc1','width':out['width'],'height':out['height'],'duration':after,'createdAt':store.now()}
            side=derived.with_suffix('.part.json');side.write_text(json.dumps(meta,ensure_ascii=False),'utf-8');side.replace(derived.with_suffix('.json'))
            return derived
        finally:
            derived.with_suffix('.part.mp4').unlink(missing_ok=True)
            raw.unlink(missing_ok=True)
