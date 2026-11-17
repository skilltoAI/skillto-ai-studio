"""Loopback download queue and persistent video breakdown workspace (stdlib)."""
from __future__ import annotations
import argparse
import concurrent.futures
from contextlib import contextmanager
import hmac
import ipaddress
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import socket
import sqlite3
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs, urlencode

from browser_transfers import BrowserTransfers

ASSETS = Path(__file__).resolve().parents[1] / 'assets'

def extension_directory():
    selected = os.environ.get('SKILLTO_CAT_EXTENSION_DIR')
    if selected:
        directory = Path(selected).resolve()
        if (directory / 'manifest.json').is_file(): return directory
    return ASSETS / 'extension'

def public_url(value):
    if not isinstance(value, str) or len(value) > 16384:
        raise ValueError('视频链接无效')
    p = urlsplit(value)
    if p.scheme not in ('https', 'http') or not p.hostname or p.username or p.password or p.port not in (None, 80, 443):
        raise ValueError('只接受公网 HTTP/HTTPS 视频链接')
    addresses = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == 'https' else 80), type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('不能下载本机或内网地址')
    return value

def safe_source(value):
    p = urlsplit(value)
    allowed = ('v',) if p.hostname in ('youtube.com', 'www.youtube.com', 'm.youtube.com') else ()
    if p.hostname in ('douyin.com', 'www.douyin.com'): allowed = ('modal_id', 'vid')
    query = parse_qs(p.query)
    return p._replace(query=urlencode({key: query[key][0] for key in allowed if key in query}), fragment='').geturl()

class Workspace(BrowserTransfers):
    def __init__(self, root):
        self.root = Path(root).resolve() / 'workbench'
        self.root.mkdir(parents=True, exist_ok=True)
        self.lease = (self.root / 'service.lock').open('a+b')
        if self.lease.seek(0, os.SEEK_END) == 0: self.lease.write(b'0'); self.lease.flush()
        self.lease.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.lease.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lease.close()
            raise ValueError('此数据目录已有拉片服务运行，请使用原服务，或停止独立服务后再启用集成模式') from None
        self.db = self.root / 'records.sqlite3'
        self.lock = threading.RLock()
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.pending = 0
        token_file = self.root / 'pairing-token.txt'
        if not token_file.exists():
            token_file.write_text(secrets.token_urlsafe(32), encoding='utf-8')
            if os.name != 'nt': token_file.chmod(0o600)
        self.token = token_file.read_text(encoding='utf-8').strip()
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            for row in db.execute('SELECT id,data FROM records').fetchall():
                item = json.loads(row[1])
                if item['status'] in ('queued', 'downloading'):
                    item.update(status='failed', error='服务曾停止，请重新提交下载')
                    db.execute('UPDATE records SET data=? WHERE id=?', (json.dumps(item, ensure_ascii=False), row[0]))

        self.init_transfers()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db, timeout=15)
        try:
            with connection: yield connection
        finally: connection.close()

    def close(self):
        self.pool.shutdown(wait=True)
        if not self.lease.closed:
            self.lease.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.lease.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lease, fcntl.LOCK_UN)
            self.lease.close()

    def save(self, item):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO records VALUES (?,?)', (item['id'], json.dumps(item, ensure_ascii=False)))

    def items(self):
        with self.connect() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT data FROM records ORDER BY rowid DESC')]

    def get(self, record_id):
        with self.connect() as db:
            row = db.execute('SELECT data FROM records WHERE id=?', (record_id,)).fetchone()
        if not row: raise ValueError('记录不存在')
        return json.loads(row[0])

    def submit(self, args, browser=False):
        if args.get('authorized') is not True: raise ValueError('请确认你有权下载此视频')
        url = public_url(args.get('url', ''))
        source = public_url(args.get('sourceUrl') or url)
        title = args.get('title', '未命名视频')
        if not isinstance(title, str): raise ValueError('标题无效')
        with self.lock:
            if sum(row.get('status') in ('queued', 'downloading') for row in self.items() + self.export_items()) >= 20:
                raise ValueError('待下载任务已满，请稍后再试')
            item = {'id': str(uuid.uuid4()), 'title': title[:300], 'sourceUrl': safe_source(source),
                    'platform': urlsplit(source).hostname, 'createdAt': datetime.now(timezone.utc).isoformat(),
                    'status': 'queued', 'error': '', 'notes': '', 'shots': [], 'revision': 0, 'history': []}
            if browser:
                return self.begin_browser(item, args, url)
            self.save(item)
            self.pending += 1
            self.pool.submit(self.download, item['id'], url, source)
        return item

    def patch(self, args):
        with self.lock:
            item = self.get(args['id'])
            if args.get('revision') != item['revision']: raise ValueError('记录已更新，请刷新后保存')
            notes, shots = args.get('notes', ''), args.get('shots', [])
            if not isinstance(notes, str) or len(notes) > 100000 or not isinstance(shots, list) or len(shots) > 2000:
                raise ValueError('笔记或分镜格式无效')
            clean = []
            for shot in shots:
                if not isinstance(shot, dict): raise ValueError('分镜格式无效')
                start, end = shot.get('start'), shot.get('end')
                if (isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, (int, float))
                        or not isinstance(end, (int, float)) or not 0 <= start < end < 86400):
                    raise ValueError('分镜时间必须为秒数，结束时间大于开始时间')
                text = shot.get('text', '')
                if not isinstance(text, str) or len(text) > 10000: raise ValueError('分镜描述无效')
                clean.append({'start': start, 'end': end, 'text': text})
            item['history'].append({'at': datetime.now(timezone.utc).isoformat(), 'notes': item['notes'], 'shots': item['shots'], 'revision': item['revision']})
            item.update(notes=notes, shots=clean, revision=item['revision'] + 1)
            self.save(item)
            return item

    def download(self, record_id, url, source):
        folder = self.root / 'media' / record_id
        folder.mkdir(parents=True, exist_ok=True)
        try:
            with self.lock:
                item = self.get(record_id); item['status'] = 'downloading'; self.save(item)
            payload = {'url': url, 'source': source, 'folder': str(folder)}
            process = subprocess.Popen([sys.executable, str(Path(__file__).with_name('download_worker.py'))],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, encoding='utf-8', cwd=folder, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            try:
                output, _ = process.communicate(json.dumps(payload), timeout=1200)
            except subprocess.TimeoutExpired:
                process.kill(); process.communicate(); raise ValueError('下载超过 20 分钟，已停止')
            result = json.loads(output)
            if process.returncode or not result.get('ok'):
                raise ValueError(result.get('error', '下载失败，请检查依赖或平台访问权限'))
            file = (folder / result['file']).resolve()
            if file.parent != folder.resolve() or not file.is_file(): raise ValueError('未生成可播放的视频')
            with self.lock:
                item = self.get(record_id)
                item.update(status='ready', title=str(result.get('title') or item['title'])[:300],
                            duration=result.get('duration'), width=result.get('width'), height=result.get('height'),
                            file=file.name, bytes=file.stat().st_size)
                self.save(item)
        except Exception as exc:
            message = str(exc) if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError) else '下载失败，请检查 yt-dlp、FFmpeg 和平台访问权限'
            with self.lock:
                item = self.get(record_id); item.update(status='failed', error=message[:300]); self.save(item)
        finally:
            with self.lock: self.pending -= 1

    def media(self, record_id):
        item = self.get(record_id)
        if item['status'] != 'ready': raise ValueError('视频尚未下载完成')
        folder = (self.root / 'media' / record_id).resolve()
        file = (folder / item['file']).resolve()
        if not folder.is_relative_to(self.root / 'media') or file.parent != folder or not file.is_file():
            raise ValueError('视频文件不存在')
        return file

_workspaces = {}
_guard = threading.Lock()
def workspace():
    root = str(Path(os.environ.get('SKILLTO_TABLE_ROOT', Path.home() / 'skillto-table-data')).resolve())
    with _guard:
        if root not in _workspaces: _workspaces[root] = Workspace(root)
        return _workspaces[root]

class WorkbenchMixin:
    def wb_local(self):
        authority = f'127.0.0.1:{self.server.server_port}'
        return (self.headers.get('Host') == authority and
                self.headers.get('Origin', 'http://' + authority) == 'http://' + authority and
                self.headers.get('Sec-Fetch-Site', 'same-origin') in ('same-origin', 'none'))

    def wb_auth(self):
        return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}' and hmac.compare_digest(
            self.headers.get('Authorization', ''), 'Bearer ' + workspace().token)

    def wb_send(self, data, content_type='application/json; charset=utf-8', status=200):
        body = json.dumps(data, ensure_ascii=False).encode() if not isinstance(data, bytes) else data
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; media-src 'self'; img-src 'self'; frame-ancestors 'none'")
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        p = urlsplit(self.path)
        if p.path not in ('/breakdowns', '/workbench.js', '/workbench.css', '/workbench-logo.png', '/workbench-install', '/workbench-install.js', '/api/workbench/extension-info', '/api/workbench/pairing', '/api/workbench/records', '/api/workbench/media', '/api/workbench/export-media', '/api/workbench/transfers', '/api/workbench/health'):
            return super().do_GET()
        try:
            if p.path == '/api/workbench/health':
                if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}': raise PermissionError()
                import importlib.util
                from dependencies import ffmpeg_path
                version = json.loads((ASSETS / 'extension' / 'manifest.json').read_text(encoding='utf-8'))['version']
                return self.wb_send({'service': 'skillto-int-workbench', 'ytDlp': bool(importlib.util.find_spec('yt_dlp')), 'ffmpeg': bool(ffmpeg_path()), 'extensionVersion': version,
                    'features': {'clipExports': True, 'independentExports': True, 'catIntegration': True, 'browserUpload': True}})
            if p.path == '/api/workbench/pairing':
                if not self.wb_local(): raise PermissionError()
                return self.wb_send({'token': workspace().token})
            if p.path == '/api/workbench/records':
                if not (self.wb_local() or self.wb_auth()): raise PermissionError()
                return self.wb_send({'records': workspace().items()})
            if p.path == '/api/workbench/transfers':
                if not (self.wb_local() or self.wb_auth()): raise PermissionError()
                query = parse_qs(p.query)
                item = workspace().transfer_get(query.get('id', [''])[0], query.get('destination', ['workbench'])[0])
                fields = ('id', 'title', 'status', 'phase', 'error', 'duration', 'width', 'height', 'bytes', 'file', 'destination', 'clipStart', 'clipEnd')
                return self.wb_send({key: item[key] for key in fields if key in item})
            media_route = p.path in ('/api/workbench/media', '/api/workbench/export-media')
            if not (self.wb_local() or (media_route and self.wb_auth())): raise PermissionError()
            if p.path == '/api/workbench/extension-info':
                directory = extension_directory()
                manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
                return self.wb_send({'version': manifest.get('version_name', manifest['version']), 'name': manifest['name'], 'directory': str(directory.resolve())})
            if media_route:
                record_id = parse_qs(p.query).get('id', [''])[0]
                file = workspace().export_media(record_id) if p.path.endswith('export-media') else workspace().media(record_id)
                size = file.stat().st_size; start, end = 0, size - 1
                header = self.headers.get('Range')
                if header:
                    match = re.fullmatch(r'bytes=(\d*)-(\d*)', header)
                    if not match or not any(match.groups()): raise ValueError('无效的播放范围')
                    if match[1]:
                        start = int(match[1]); end = min(int(match[2]), size - 1) if match[2] else size - 1
                    else: start = max(0, size - int(match[2]))
                    if start > end or start >= size:
                        self.send_response(416); self.send_header('Content-Range', f'bytes */{size}'); self.end_headers(); return
                self.send_response(206 if header else 200)
                self.send_header('Content-Type', mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
                self.send_header('Accept-Ranges', 'bytes'); self.send_header('Content-Length', str(end-start+1))
                if header: self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
                self.end_headers()
                with file.open('rb') as stream:
                    stream.seek(start); remaining = end-start+1
                    while remaining:
                        chunk = stream.read(min(1024*1024, remaining))
                        if not chunk: break
                        self.wfile.write(chunk); remaining -= len(chunk)
                return
            names = {'/breakdowns': 'workbench.html', '/workbench-logo.png': 'extension/icons/128.png',
                     '/workbench-install': 'extension-install.html', '/workbench-install.js': 'extension-install.js'}
            file = ASSETS / names.get(p.path, p.path[1:])
            self.wb_send(file.read_bytes(), mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
        except PermissionError: self.wb_send({'error': '请从本机工作台访问，或检查插件连接码'}, status=403)
        except ValueError as exc: self.wb_send({'error': str(exc)}, status=400)
        except OSError: self.wb_send({'error': '请求无效或文件不存在'}, status=400)

    def do_POST(self):
        if urlsplit(self.path).path == '/api/workbench/browser-upload':
            try:
                if not self.wb_auth(): raise PermissionError()
                if self.headers.get('Content-Type', '').split(';')[0] != 'application/octet-stream':
                    raise ValueError('需要视频数据')
                query = parse_qs(urlsplit(self.path).query)
                length = int(self.headers.get('Content-Length', '-1'))
                if not 0 <= length <= 4 * 1024**2: raise ValueError('视频数据块过大')
                data = self.rfile.read(length)
                if len(data) != length: raise ValueError('视频传输中断')
                return self.wb_send(workspace().upload_browser(query.get('id', [''])[0],
                    query.get('destination', ['workbench'])[0], int(query.get('offset', ['-1'])[0]), data,
                    final=query.get('final') == ['1']))
            except PermissionError: return self.wb_send({'error': '工作台连接已失效'}, status=403)
            except (ValueError, KeyError, OSError): return self.wb_send({'error': '视频传输失败，请重新同步'}, status=400)
        if urlsplit(self.path).path == '/api/workbench/extension-setup':
            if not self.wb_local(): return self.wb_send({'error': '请从本机工作台打开安装入口'}, status=403)
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.wb_send({'error': '需要本机 JSON 请求'}, status=400)
            try:
                from extension_setup import open_setup
                open_setup(extension_directory())
                return self.wb_send({'ok': True})
            except (OSError, ValueError): return self.wb_send({'error': '请在 Chrome 地址栏打开 chrome://extensions'}, status=400)
        if urlsplit(self.path).path != '/api/workbench/records': return super().do_POST()
        try:
            if not (self.wb_local() or self.wb_auth()): raise PermissionError()
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json': raise ValueError('需要 JSON 请求')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 500000: raise ValueError('请求过大')
            args = json.loads(self.rfile.read(length))
            if not isinstance(args, dict): raise ValueError('请求无效')
            if args.get('action') == 'create': result = workspace().submit(args)
            elif args.get('action') == 'browser-start': result = workspace().submit(args, browser=True)
            elif args.get('action') == 'browser-finish': result = workspace().finish_browser(args)
            elif args.get('action') == 'update': result = workspace().patch(args)
            else: raise ValueError('未知操作')
            self.wb_send(result)
        except PermissionError: self.wb_send({'error': '连接码无效'}, status=403)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            self.wb_send({'error': str(exc) if isinstance(exc, ValueError) else '请求失败'}, status=400)

class StandaloneBase(BaseHTTPRequestHandler):
    def do_GET(self):
        if urlsplit(self.path).path == '/':
            self.send_response(302); self.send_header('Location', '/breakdowns'); self.end_headers()
        else: self.send_error(404)

    def do_POST(self): self.send_error(404)

class Handler(WorkbenchMixin, StandaloneBase):
    def log_message(self, *args): pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8891)
    parser.add_argument('--data-root', type=Path)
    args = parser.parse_args()
    if args.data_root: os.environ['SKILLTO_TABLE_ROOT'] = str(args.data_root.resolve())
    workspace()
    with ThreadingHTTPServer(('127.0.0.1', args.port), Handler) as server:
        print(f'Skillto.ai工作台: http://127.0.0.1:{args.port}/breakdowns', flush=True)
        server.serve_forever()
