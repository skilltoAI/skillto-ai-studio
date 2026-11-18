"""ASGI adapter for migrated native HTML/JS and existing module handlers."""
import email.message
import importlib.util
import io
import json
import mimetypes
import os
from pathlib import Path
import re
import tempfile
import threading
from types import SimpleNamespace
from urllib.parse import urlsplit, parse_qs

from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse
import legacy_assets

HERE = Path(__file__).parent
ASSETS = HERE/'modules/table/assets'


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
            if 'text/html' in content_type and b'workspace-nav.js' not in body:
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
                    f"frame-src 'self' {metabase}; frame-ancestors {ancestors}")
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',len(body))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            if attachment: self.send_header('Content-Disposition','attachment; filename="'+attachment+'"')
            self.wfile.write(body)
        def do_GET(self):
            parsed=urlsplit(self.path); path=parsed.path; query=parse_qs(parsed.query)
            if path == '/':
                page=(base.ASSETS/'index.html').read_text('utf-8')
                extra=''
                for stem in ('schema-controls','table-lineage','workspace-nav','report-system','rewrite-system','studio-theme','studio-shell','motion-system'):
                    for extension in ('css','js'):
                        asset=ASSETS/(stem+'.'+extension)
                        if asset.is_file() or stem=='motion-system':
                            extra += ('<link rel="stylesheet" href="/'+stem+'.css">' if extension=='css' else '<script src="/'+stem+'.js" defer></script>')
                extra += '<script src="/schema-editor.js" defer></script>'
                page=page.replace('</head>',extra+'</head>').replace('抖音账号表','个人工作台')
                return self.respond(page.encode(),'text/html; charset=utf-8')
            if path.startswith('/api/motions/') or path in ('/motion-system.js','/motion-system.css'):
                return self.motion_get()
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
