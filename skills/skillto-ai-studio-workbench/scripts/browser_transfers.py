"""Browser download import and selected-range exports; no remote fetching."""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import shutil
from urllib.parse import urlsplit


class BrowserTransfers:
    def upload_browser(self, record_id, destination, offset, data, final=False):
        """Authenticated, ordered chunks; the caller never supplies a local path."""
        with self.lock:
            item = self.transfer_get(record_id, destination)
            if item.get('transfer') != 'browser' or item['status'] != 'downloading' or item.get('browserImporting'):
                raise ValueError('任务已结束或正在处理')
            if item.get('phase') != 'receiving': raise ValueError('任务已开始处理')
            folder = self.root / 'incoming' / item['id'] / 'SkilltoWorkbench'
            for part in (folder, *folder.parents):
                if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
                    raise ValueError('不能写入链接目录')
            folder.mkdir(parents=True, exist_ok=True)
            part = folder / (item['browserFilename'] + '.part')
            if part.is_symlink(): raise ValueError('不能写入链接文件')
            size = part.stat().st_size if part.exists() else 0
            if offset != size: raise ValueError('视频传输位置不一致，请重新同步')
            if not final:
                if not 0 < len(data) <= 4 * 1024**2 or size + len(data) > 2 * 1024**3:
                    raise ValueError('视频超过允许的传输大小')
                with part.open('ab') as out: out.write(data)
                item.update(receivedBytes=size + len(data), uploadMode=True); self.transfer_save(item)
                return {'receivedBytes': item['receivedBytes']}
            if data or not size: raise ValueError('视频尚未传输完成')
            source = folder / item['browserFilename']
            part.replace(source)
        return self.finish_browser({'id': record_id, 'destination': destination, 'filename': str(source)})

    def init_transfers(self):
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS exports (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            for record_id, data in db.execute('SELECT id,data FROM exports').fetchall():
                item = json.loads(data)
                if item.get('status') in ('queued', 'downloading'):
                    item.update(status='failed', error='服务曾停止，请重新导出片段')
                    db.execute('UPDATE exports SET data=? WHERE id=?', (json.dumps(item, ensure_ascii=False), record_id))

    def export_items(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT data FROM exports')]

    def transfer_get(self, record_id, destination='workbench'):
        if destination == 'workbench': return self.get(record_id)
        if destination != 'download': raise ValueError('下载目标无效')
        with self.connect() as db:
            row = db.execute('SELECT data FROM exports WHERE id=?', (record_id,)).fetchone()
        if not row: raise ValueError('导出任务不存在')
        return json.loads(row[0])

    def transfer_save(self, item):
        if item.get('destination') != 'download': return self.save(item)
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO exports VALUES (?,?)', (item['id'], json.dumps(item, ensure_ascii=False)))

    def begin_browser(self, item, args, url):
        destination = args.get('destination', 'workbench')
        if destination not in ('download', 'workbench'): raise ValueError('下载目标无效')
        start, end = args.get('clipStart'), args.get('clipEnd')
        if start is not None or end is not None:
            if (isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, (int, float))
                    or not isinstance(end, (int, float)) or not math.isfinite(start) or not math.isfinite(end)
                    or not 0 <= start < end <= 86400):
                raise ValueError('片段范围无效，请检查开始和结束时间')
            item.update(clipStart=start, clipEnd=end)
        elif destination == 'download':
            raise ValueError('完整文件请直接使用浏览器下载')
        extension = 'webm' if urlsplit(url).path.lower().endswith('.webm') else 'mp4'
        item.update(status='downloading', transfer='browser', destination=destination,
                    phase='receiving', browserFilename=f"{item['id']}.{extension}")
        duration = args.get('duration')
        if isinstance(duration, (int, float)) and not isinstance(duration, bool) and 0 < duration < 86400:
            if end is not None and end > duration + 0.1: raise ValueError('片段结束时间超过视频时长')
            item['expectedDuration'] = duration
        self.transfer_save(item)
        return item

    def finish_browser(self, args):
        destination = args.get('destination', 'workbench')
        with self.lock:
            item = self.transfer_get(args['id'], destination)
            if item.get('transfer') != 'browser': raise ValueError('不是浏览器下载任务')
            if item['status'] in ('ready', 'failed') or item.get('browserImporting'): return item
            if args.get('failed') is True:
                item.update(status='failed', phase='failed', error='视频传输未完成，请重新同步' if item.get('uploadMode') else '浏览器下载未完成，请在 Chrome 下载列表检查原因')
                self.transfer_save(item); return item
            item['browserImporting'] = True; self.transfer_save(item)
        try:
            value = args.get('filename')
            if not isinstance(value, str) or len(value) > 4096: raise ValueError('下载文件无效')
            source = Path(value)
            if (not source.is_absolute() or str(source).startswith(('\\\\', '//'))
                    or source.name != item['browserFilename'] or source.parent.name != 'SkilltoWorkbench'):
                raise ValueError('下载文件不属于本次任务')
            for part in (source, *source.parents):
                if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
                    raise ValueError('不能导入链接文件')
            stat = source.stat()
            if not source.is_file() or not 0 < stat.st_size <= 2 * 1024**3: raise ValueError('文件大小无效')
            if stat.st_mtime < datetime.fromisoformat(item['createdAt']).timestamp() - 5: raise ValueError('文件不是本次下载')
            from download_worker import probe_media
            metadata = probe_media(source)
            if not metadata.get('width') or not metadata.get('height'): raise ValueError('文件不是有效视频')
            expected, actual = item.get('expectedDuration'), metadata.get('duration')
            if expected and actual and actual < expected - max(2, expected * 0.1): raise ValueError('视频下载不完整')
            if item.get('clipEnd') is not None and (not actual or item['clipEnd'] > actual + 0.1):
                raise ValueError('选区超出实际视频长度')
            with self.lock:
                item = self.transfer_get(item['id'], destination)
                item.update(phase='processing', sourceDuration=actual); self.transfer_save(item)
            self.pool.submit(self.process_browser, item['id'], destination, source)
        except (OSError, ValueError):
            with self.lock:
                item = self.transfer_get(item['id'], destination)
                item.update(status='failed', browserImporting=False,
                    error='视频导入失败：文件须为本次下载的完整视频，选区不能超出时长；原文件保留在浏览器下载目录')
                self.transfer_save(item)
        return item

    def process_browser(self, record_id, destination, source):
        try:
            item = self.transfer_get(record_id, destination)
            folder = self.root / ('exports' if destination == 'download' else 'media') / record_id
            folder.mkdir(parents=True, exist_ok=True)
            clipped = item.get('clipEnd') is not None
            target = folder / ('video.mp4' if clipped else 'video' + source.suffix)
            temporary = folder / ('processing.mp4' if clipped else 'browser-import.part')
            if clipped:
                from clip_media import cut_video
                cut_video(source, temporary, item['clipStart'], item['clipEnd'])
            else: shutil.copyfile(source, temporary)
            from download_worker import probe_media
            metadata = probe_media(temporary)
            if not metadata.get('width') or not temporary.stat().st_size: raise ValueError('未生成有效视频')
            if clipped and abs(metadata.get('duration', 0) - (item['clipEnd'] - item['clipStart'])) > 0.25:
                raise ValueError('片段长度不完整')
            temporary.replace(target)
            with self.lock:
                item = self.transfer_get(record_id, destination)
                item.update(status='ready', phase='ready', error='', browserImporting=False,
                            file=target.name, bytes=target.stat().st_size, **metadata)
                self.transfer_save(item)
        except Exception:
            with self.lock:
                item = self.transfer_get(record_id, destination)
                item.update(status='failed', phase='failed', browserImporting=False,
                            error='视频处理失败，请检查选区、FFmpeg 和磁盘空间；原下载文件保留')
                self.transfer_save(item)

    def export_media(self, record_id):
        item = self.transfer_get(record_id, 'download')
        if item['status'] != 'ready': raise ValueError('片段尚未处理完成')
        folder = self.root / 'exports' / record_id
        file = (folder / item['file']).resolve()
        if file.parent != folder.resolve() or not file.is_file(): raise ValueError('片段文件不存在')
        return file
