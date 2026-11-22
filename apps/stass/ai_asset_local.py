"""Local red-white topics and resumable MCP media intake."""
import base64
import binascii
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile


MAX_VIDEO = 512 * 1024 * 1024
CHUNK_BYTES = 512 * 1024
OPERATIONS = {'create_topic', 'begin_upload', 'upload_chunk', 'finish_upload', 'abort_upload'}


def stable_id(*parts):
    return hashlib.sha256('\0'.join(parts).encode('utf-8')).hexdigest()[:24]


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{24}', value):
        raise ValueError('无效的本机资产标识')
    return value


def video_path(store, ident):
    return store.ROOT / 'ai-asset-media' / (identifier(ident) + '.mp4')


def cover_path(store, ident):
    return video_path(store, ident).with_suffix('.jpg')


def set_cover(args, store):
    from ai_asset_library import get_local_asset
    from dependencies import ffmpeg_path

    ident = identifier(args.get('itemId'))
    time_ms = args.get('timeMs')
    if type(time_ms) is not int or not 0 <= time_ms <= 86_400_000:
        raise ValueError('需要有效的视频帧时间（毫秒）')
    source = video_path(store, ident)
    if get_local_asset(ident, store) is None or not source.is_file():
        raise ValueError('本机视频不存在')
    ffmpeg = ffmpeg_path()
    if not ffmpeg:
        raise ValueError('生成视频封面需要 FFmpeg')

    # Decode only the registered local MP4. Keep the selected frame in memory
    # until encoding succeeds, so a failed replacement leaves the old cover intact.
    try:
        result = subprocess.run([
            ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error',
            '-protocol_whitelist', 'file', '-f', 'mov', '-ss', f'{time_ms / 1000:.3f}',
            '-i', str(source), '-map', '0:v:0', '-frames:v', '1',
            '-vf', 'scale=960:540:force_original_aspect_ratio=increase:force_divisible_by=2,crop=960:540,setsar=1',
            '-threads', '1', '-c:v', 'mjpeg', '-q:v', '3', '-f', 'image2pipe', 'pipe:1',
        ], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=20, check=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError('无法从本机视频提取封面') from exc
    if not result.stdout.startswith(b'\xff\xd8'):
        raise ValueError('该时间点没有可用的视频帧')

    target = cover_path(store, ident)
    with tempfile.TemporaryDirectory(dir=target.parent, prefix='cover-') as staging:
        staged = Path(staging) / 'cover.jpg'
        staged.write_bytes(result.stdout)
        os.replace(staged, target)
    return {'itemId': ident, 'timeMs': time_ms, 'hasCover': True}


def dispatch(args, store, path, data):
    # The library holds its cross-process write lock for the entire operation.
    from ai_asset_library import text

    topics = data.setdefault('localTopics', [])
    items = data.setdefault('localItems', [])
    action = args['action']
    if action == 'create_topic':
        if args.get('library', 'red-white') != 'red-white':
            raise ValueError('本机 Topic 当前支持 AI红白模库')
        title = text(args.get('title'), 200, 'Topic 名称')
        if not title:
            raise ValueError('Topic 名称不能为空')
        topic = {'id': stable_id('local-topic', title.casefold()), 'title': title, 'library': 'red-white'}
        existing = next((item for item in topics if item['id'] == topic['id']), None)
        if existing is None and not args.get('dryRun'):
            topics.append(topic)
            store.write_json(path, data)
        return {'topic': existing or topic, 'created': existing is None and not args.get('dryRun'),
                'dryRun': bool(args.get('dryRun'))}

    if action == 'begin_upload':
        topic_id = identifier(args.get('topicId'))
        if not any(topic['id'] == topic_id for topic in topics):
            raise ValueError('本机 Topic 不存在')
        key = text(args.get('itemKey'), 100, '条目幂等键')
        title = text(args.get('title'), 200, '条目名称')
        filename = text(args.get('filename'), 255, '视频文件名')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', key) or not title:
            raise ValueError('需要有效的条目键和名称')
        if not filename.lower().endswith('.mp4') or re.search(r'[\\/:\x00-\x1f]', filename):
            raise ValueError('请提供 MP4 文件的名称，不带路径')
        size = args.get('size')
        digest = args.get('sha256')
        if type(size) is not int or not 12 <= size <= MAX_VIDEO:
            raise ValueError('MP4 大小超出允许范围')
        if not isinstance(digest, str) or not re.fullmatch(r'[a-f0-9]{64}', digest):
            raise ValueError('需要文件的 SHA-256')
        ident = stable_id('local-video', topic_id, key)
        item = {'id': ident, 'topicId': topic_id, 'library': 'red-white', 'title': title,
                'description': text(args.get('description', ''), 1000, '摘要'),
                'prompt': text(args.get('prompt', ''), 40000, '提示词'), 'filename': filename,
                'size': size, 'mediaDigest': digest, 'playback': 'local-file', 'references': []}
    else:
        ident = identifier(args.get('uploadId'))

    target = video_path(store, ident)
    part = target.with_suffix('.part')
    ticket = target.with_suffix('.json')
    saved = next((entry for entry in items if entry['id'] == ident), None)
    if saved is not None:
        if action == 'begin_upload' and saved != item:
            raise ValueError('条目键已用于其他内容')
        if action == 'abort_upload':
            raise ValueError('已入库视频不能通过取消上传删除')
        return {'uploadId': ident, 'offset': saved['size'], 'complete': True, 'item': saved}
    if action == 'begin_upload':
        if ticket.exists() and store.read_json(ticket) != item:
            raise ValueError('同一条目已有不同的上传内容')
        if not args.get('dryRun') and not ticket.exists():
            ticket.parent.mkdir(parents=True, exist_ok=True)
            store.write_json(ticket, item)
        offset = target.stat().st_size if target.exists() else part.stat().st_size if part.exists() else 0
        return {'uploadId': ident, 'offset': offset, 'complete': False, 'chunkBytes': CHUNK_BYTES,
                'dryRun': bool(args.get('dryRun'))}
    if not ticket.is_file():
        if action == 'abort_upload':
            return {'uploadId': ident, 'aborted': True}
        raise ValueError('上传任务不存在')
    item = store.read_json(ticket)
    if action == 'abort_upload':
        part.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        ticket.unlink()
        return {'uploadId': ident, 'aborted': True}
    if action == 'upload_chunk':
        payload = args.get('base64')
        offset = args.get('offset')
        if not isinstance(payload, str) or len(payload) > 4 * ((CHUNK_BYTES + 2) // 3) or type(offset) is not int:
            raise ValueError('无效的上传分块')
        try:
            chunk = base64.b64decode(payload, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError('无效的 base64 分块') from exc
        current_file = target if target.exists() else part
        current = current_file.stat().st_size if current_file.exists() else 0
        if not 0 <= offset <= current or not 1 <= len(chunk) <= CHUNK_BYTES or offset + len(chunk) > item['size']:
            raise ValueError('分块偏移或长度不符合上传进度')
        if offset < current:
            with current_file.open('rb') as stream:
                stream.seek(offset)
                existing = stream.read(len(chunk))
            if existing != chunk[:len(existing)]:
                raise ValueError('重试数据与已上传内容不匹配')
            chunk = chunk[len(existing):]
        if chunk:
            with part.open('ab') as stream:
                stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())
        return {'uploadId': ident, 'offset': current + len(chunk), 'complete': False}
    media = target if target.exists() else part
    if not media.is_file() or media.stat().st_size != item['size']:
        raise ValueError('视频尚未上传完整')
    with media.open('rb') as stream:
        if stream.read(12)[4:8] != b'ftyp':
            raise ValueError('文件没有 MP4 容器标识')
        stream.seek(0)
        if hashlib.file_digest(stream, 'sha256').hexdigest() != item['mediaDigest']:
            raise ValueError('视频 SHA-256 校验失败')
    if media != target:
        os.replace(media, target)
    items.append(item)
    store.write_json(path, data)
    ticket.unlink(missing_ok=True)
    return {'uploadId': ident, 'offset': item['size'], 'complete': True, 'item': item}
