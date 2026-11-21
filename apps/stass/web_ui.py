"""ASGI adapter for migrated native HTML/JS and existing module handlers."""
import email.message
from html import escape
import importlib.util
import io
import json
import mimetypes
import os
from pathlib import Path
import re
import tempfile
import threading
import uuid
from types import SimpleNamespace
from urllib.parse import urlsplit, parse_qs

from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse
import legacy_assets
import ai_asset_library
import red_white_cloud
import work_profiles
from runtime_state import atomic_json

HERE = Path(__file__).parent
ASSETS = HERE/'modules/table/assets'
FEATURE_UI = HERE/'modules/table/scripts/windows/ui'


def prefix_text(text):
    # Match URL literals, including template literals and existing pathname checks.
    return re.sub(r'''(["'`])/((?!/|STASS/)[A-Za-z?][^\s"'`]*|)(?=["'`])''',
                  lambda m: m[1]+'/STASS/'+('api/v1/'+m[2][4:] if m[2].startswith('api/') else m[2]), text).replace('url(/', 'url(/STASS/')


def create_endpoint(store, rewrites, reports, motions, workbench, data):
    os.environ['STASS_RESOURCE_ROOT'] = str(data/'resources')
    spec = importlib.util.spec_from_file_location('stass_review_web', HERE/'modules/table/base/review_web.py')
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    base._STORE = store
    import rewrite_voice
    from browser_profiles import BrowserProfiles
    browser_manager = None
    browser_lock=threading.Lock()
    document_lock = threading.Lock()
    document_path = data / 'document-links.json'

    def document_links():
        if not document_path.exists():
            return []
        return json.loads(document_path.read_text(encoding='utf-8'))

    def change_document(request):
        with document_lock:
            items = document_links()
            if request.get('action') == 'remove':
                items = [item for item in items if item['id'] != request.get('id')]
            elif request.get('action') == 'add':
                title, url = (request.get(key) for key in ('title', 'url'))
                if not isinstance(title, str) or not 1 <= len(title.strip()) <= 120:
                    raise ValueError('请输入 1 至 120 个字符的文档名称。')
                if not isinstance(url, str) or len(url) > 2048 or any(c.isspace() for c in url):
                    raise ValueError('请输入有效的 HTTPS 文档链接。')
                parsed = urlsplit(url)
                if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
                    raise ValueError('请输入有效的 HTTPS 文档链接。')
                items.append({'id': str(uuid.uuid4()), 'title': title.strip(), 'url': url})
            else:
                raise ValueError('无法识别的文档操作。')
            atomic_json(document_path, items)
            return items

    class Handler(motions.MotionMixin, workbench.WorkbenchMixin, base.ReviewHandler):
        def respond_json(self, payload, status=200):
            return super().respond_json(legacy_assets.rewrite_urls(payload),status)
        def wb_send(self, value, content_type='application/json; charset=utf-8', status=200):
            return self.respond(value if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False).encode(),content_type,status)
        def send_response(self, status, message=None): self.status = status
        def send_header(self, name, value): self.response_headers[name] = str(value)
        def end_headers(self): pass
        def send_error(self, status, message=None): self.respond_json({'error':message or 'Request failed'},status)
        def log_message(self,*args): pass
        def respond(self, body, content_type, status=200, attachment=None):
            if 'text/html' in content_type and b'workspace-nav.js' not in body and urlsplit(self.path).path != '/features.html':
                body=body.replace(b'</head>', b'<link rel="stylesheet" href="/workspace-nav.css"><link rel="stylesheet" href="/studio-theme.css"><script src="/workspace-nav.js" defer></script></head>')
            if any(kind in content_type for kind in ('html','javascript','css')):
                body = prefix_text(body.decode('utf-8')).encode('utf-8')
            if 'text/html' in content_type:
                page = urlsplit(self.path)
                query = parse_qs(page.query)
                embedded_table = page.path == '/' and query.get('rewriteEmbed') == ['1'] and bool(query.get('table'))
                ancestors = "'self'" if embedded_table else "'none'"
                metabase = reports.METABASE_URL
                self.send_header('Content-Security-Policy',
                    f"default-src 'self'; img-src 'self' https: data: {metabase}; media-src 'self' https: blob:; "
                    f"script-src 'self' {metabase}; connect-src 'self' {metabase}; "
                    f"style-src 'self' 'unsafe-inline' {metabase}; font-src 'self' data: {metabase}; "
                    f"frame-src 'self' {metabase} https://www.skillto.ai; frame-ancestors {ancestors}")
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',len(body))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            if attachment: self.send_header('Content-Disposition','attachment; filename="'+attachment+'"')
            self.wfile.write(body)
        def do_GET(self):
            parsed=urlsplit(self.path); path=parsed.path; query=parse_qs(parsed.query)
            if path == '/about':
                identity = ''.join(f'<dt>{label}</dt><dd><code>{escape(os.environ.get(key) or "—")}</code></dd>'
                                   for label, key in [('版本', 'STASS_RELEASE_VERSION'),
                                                      ('源码提交', 'STASS_RELEASE_COMMIT'),
                                                      ('清单 SHA-256', 'STASS_MANIFEST_SHA256')])
                page = ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
                        '<title>关于 Skillto.ai Studio</title></head><body>'
                        '<main><h1>关于 Skillto.ai Studio</h1><dl>' + identity +
                        '</dl><p><a href="/health">服务诊断</a></p></main></body></html>')
                return self.respond(page.encode(), 'text/html; charset=utf-8')
            if path == '/api/work-navigation':
                return self.respond_json(work_profiles.dispatch({'action':'navigation'}))
            if path == '/api/document-links':
                if not self.local_peer: return self.send_error(403, '请在本机查看和管理个人文档链接。')
                return self.respond_json(document_links())
            if path in ('/features.html','/features.css','/features.js'):
                if not self.local_peer:
                    return self.send_error(403,'请在工作台所在电脑管理安装与偏好')
                types = {'.html':'text/html; charset=utf-8','.css':'text/css','.js':'text/javascript'}
                file = FEATURE_UI / path[1:]
                return self.respond(file.read_bytes(),types[file.suffix])
            if path == '/' and not query and work_profiles.profile()['groups'] is not None:
                page = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
                <meta name="viewport" content="width=device-width,initial-scale=1"><title>个人工作台</title>
                <script defer src="/profile-home.js"></script></head><body>
                <main class="profile-home"><h1>我的工作台</h1><section id="quick-actions"></section>
                <p id="quick-status" role="status"></p></main></body></html>"""
                return self.respond(page.encode(),'text/html; charset=utf-8')
            if path == '/':
                page=(base.ASSETS/'index.html').read_text('utf-8')
                extra=''
                for stem in ('schema-controls','table-lineage','workspace-nav','report-system','rewrite-system','studio-theme','studio-shell','motion-system','ai-assets'):
                    for extension in ('css','js'):
                        asset=ASSETS/(stem+'.'+extension)
                        if asset.is_file() or stem=='motion-system':
                            extra += ('<link rel="stylesheet" href="/'+stem+'.css">' if extension=='css' else '<script src="/'+stem+'.js" defer></script>')
                extra += '<script src="/schema-editor.js" defer></script>'
                page=page.replace('</head>',extra+'</head>').replace('抖音账号表','个人工作台')
                return self.respond(page.encode(),'text/html; charset=utf-8')
            if path.startswith('/api/motions/') or path in ('/motion-system.js','/motion-system.css'):
                return self.motion_get()
            if path == '/api/ai-assets/official':
                try:
                    key = query.get('topic', [''])[0]
                    return self.respond_json(red_white_cloud.official_embed(key) if key else red_white_cloud.official_list())
                except (OSError, ValueError, KeyError, TypeError):
                    return self.respond_json({'error': '官方专题暂不可用'}, 503)
            if path == '/api/ai-assets/catalog':
                return self.respond_json(ai_asset_library.dispatch({'action': 'catalog'}, store))
            if path=='/api/reports/catalog': return self.respond_json(reports.catalog())
            if path=='/api/reports/lineage': return self.respond_json(reports.lineage())
            if path=='/api/reports/item': return self.respond_json(reports.get_report(query['id'][0]))
            if path=='/api/reports/embed': return self.respond_json(reports.embed(query['id'][0]))
            if path=='/api/rewrites': return self.respond_json(rewrites.dispatch({'action':'list'}))
            if path=='/api/rewrites/voice-status':
                return self.respond_json(rewrite_voice.status(query.get('job',[''])[0],query.get('id',[''])[0],query.get('versionId',[''])[0]))
            if path=='/studio-wordmark.png':
                return self.respond((ASSETS/'brand/studio-wordmark.png').read_bytes(),'image/png')
            if path=='/browser-users':
                if not self.local_peer: return self.send_error(403,'Browser control is local only')
                return self.respond((ASSETS/'browser-users.html').read_bytes(),'text/html; charset=utf-8')
            if re.fullmatch(r'/[a-z-]+\.(js|css)',path) and (ASSETS/path[1:]).is_file():
                return self.respond((ASSETS/path[1:]).read_bytes(),'text/javascript' if path.endswith('.js') else 'text/css')
            return super().do_GET()
        def do_POST(self):
            nonlocal browser_manager
            path=urlsplit(self.path).path
            if path == '/api/document-links':
                if not self.local_peer: return self.send_error(403, '请在本机管理个人文档链接。')
                request = json.loads(self.rfile.read(8193))
                if not isinstance(request, dict): return self.send_error(400, '无效请求。')
                return self.respond_json(change_document(request))
            if path == '/api/work-preferences':
                if not self.local_peer: return self.send_error(403,'请在本机管理工作偏好')
                request = json.loads(self.rfile.read(16385))
                if not isinstance(request, dict): return self.send_error(400,'无效请求')
                return self.respond_json(work_profiles.dispatch(request))
            if path.startswith('/api/motions/'): return self.motion_post()
            if path in ('/api/rewrites','/api/rewrites/voice','/api/reports','/api/lineage','/api/browser'):
                args=json.loads(self.rfile.read())
                if path=='/api/rewrites/voice':
                    return self.respond_json(rewrite_voice.start(args.get('id',''),args.get('versionId','')))
                if path=='/api/browser':
                    if not self.local_peer: return self.send_error(403,'Browser control is local only')
                    with browser_lock:
                        if browser_manager is None: browser_manager=BrowserProfiles(data)
                    return self.respond_json({'result':browser_manager.call(args),'dataRoot':str(data)})
                callback={'/api/rewrites':rewrites.dispatch,'/api/reports':reports.dispatch,'/api/lineage':store.table_lineage}[path]
                return self.respond_json(callback(args))
            return super().do_POST()

    async def endpoint(request):
        asset_path=request.path_params.get('path','')
        if request.method in ('GET','HEAD') and asset_path.startswith(legacy_assets.FAMILIES):
            return legacy_assets.response(data,asset_path)
        pieces=[];size=0
        async for piece in request.stream():
            size+=len(piece)
            if size>10_000_000:
                from starlette.responses import JSONResponse
                return JSONResponse({'error':'Request too large'},status_code=413)
            pieces.append(piece)
        body=b''.join(pieces)
        def invoke():
            handler=Handler.__new__(Handler)
            handler.path='/'+request.path_params.get('path','')
            if handler.path.startswith('/api/v1/'): handler.path='/api/'+handler.path[len('/api/v1/'):]
            if request.url.query: handler.path+='?'+request.url.query
            handler.headers=email.message.Message()
            for key,value in request.headers.items(): handler.headers[key]=value
            handler.rfile=io.BytesIO(body)
            handler.wfile=tempfile.SpooledTemporaryFile(max_size=1024*1024)
            handler.server=SimpleNamespace(server_port=request.url.port)
            handler.local_peer=request.client is not None and request.client.host in ('127.0.0.1','::1','testclient')
            handler.status=200; handler.response_headers={}
            try:
                (handler.do_POST if request.method=='POST' else handler.do_GET)()
            except (OSError,ValueError,KeyError,TypeError) as exc:
                handler.wfile.seek(0);handler.wfile.truncate();handler.response_headers={}
                handler.respond_json({'error':str(exc)},400)
            except BaseException:
                handler.wfile.close()
                raise
            handler.wfile.seek(0)
            return handler
        handler=await run_in_threadpool(invoke)
        def chunks():
            try:
                while chunk:=handler.wfile.read(256*1024): yield chunk
            finally: handler.wfile.close()
        return StreamingResponse(chunks(),status_code=handler.status,headers=handler.response_headers)
    def close():
        if browser_manager is not None: browser_manager.close()
    endpoint.close=close
    return endpoint
