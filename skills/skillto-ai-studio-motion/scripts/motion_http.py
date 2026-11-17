"""Mixin for the existing loopback Studio service."""
import hashlib
import json
import mimetypes
import re
import secrets
import threading
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import motion_store as store
import motion_runtime as runtime
from motion_media import ensure_preview
from motion_package import MAX_PACKAGE

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
TOKEN = secrets.token_urlsafe(32)
MEDIA_LOCK = threading.Lock()

def queue_previews(ids=None):
    ids=list(dict.fromkeys(ids if ids is not None else [i['id'] for i in store.all_objects('item') if i.get('previewUrl')]))
    if not ids: return {'status':'empty'}
    for ident in ids: store.get('item',ident)
    with runtime.GUARD:
        for job in store.all_objects('job'):
            if job['kind']=='prepare_previews' and job['status'] in ('queued','running') and job['args'].get('ids')==ids:
                return job
        return runtime.submit('prepare_previews',ids[0],{'ids':ids})


def prepare_intake_media(result):
    if not result.get('dryRun'):
        try: result['mediaJob']=queue_previews([m['itemId'] for m in result['mapping']])
        except ValueError as exc: result['mediaError']=str(exc)  # metadata commit already succeeded
    return result


def dispatch(args):
    action = args.get('action')
    if action == 'catalog': return store.catalog()
    if action == 'sync_index':
        from motion_index import sync_library
        return prepare_intake_media(sync_library(bool(args.get('dryRun'))))
    if action == 'ingest':
        from motion_intake import ingest
        return prepare_intake_media(ingest(args.get('batch'),bool(args.get('dryRun'))))
    if action == 'search_index':
        import sys
        python=runtime.config().get('indexPython',sys.executable)
        result=subprocess.run([python,str(Path(__file__).with_name('motion_index.py')),'search','--query',str(args.get('query',''))[:500],'--limit','100'],capture_output=True,encoding='utf-8',timeout=60,creationflags=subprocess.CREATE_NO_WINDOW if __import__('os').name=='nt' else 0)
        if result.returncode:raise ValueError('语义检索暂不可用，请使用关键词搜索')
        return {'ids':[d['id'] for d in json.loads(result.stdout)]}
    if action == 'prepare_previews': return queue_previews(args.get('ids'))
    if action == 'seed': return store.seed()
    if action == 'add': return store.add(args)
    if action == 'update': return store.update_item(args['id'], args)
    if action == 'view': return store.mark_viewed(args['id'])
    if action == 'tag': return store.tag_action(args.get('operation','save'), args)
    if action == 'doctor': return runtime.doctor()
    if action in ('download','import','render'): return runtime.submit(action, args['id'], args)
    if action == 'cancel': return runtime.cancel(args['id'])
    if action == 'retry':
        job = store.get('job', args['id'])
        if job['status'] not in ('failed','cancelled'): raise ValueError('仅失败或取消的任务可重试')
        return runtime.submit(job['kind'], job['itemId'], job['args'])
    if action == 'remove':
        item=store.get('item',args['id'])
        if any(j['itemId']==item['id'] and j['status'] in ('queued','running','cancelling') for j in store.all_objects('job')):
            raise ValueError('请先取消此模板的活动任务')
        store.write('item',item,delete=True)
        return {'removed':item['id'],'filesPreserved':True}
    raise ValueError('未知 Motion 操作')

class MotionMixin:
    def motion_json(self, data, status=200):
        self.respond(json.dumps(data,ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8', status)

    def motion_file(self, path):
        path=Path(path)
        if not path.is_file(): return self.motion_json({'error':'文件不存在'},404)
        size=path.stat().st_size; start,end=0,size-1
        raw=self.headers.get('Range')
        if raw:
            match=re.fullmatch(r'bytes=(\d+)-(\d*)',raw)
            if not match: return self.motion_json({'error':'Range 无效'},416)
            start=int(match[1]);end=min(int(match[2]),end) if match[2] else end
            if start>end or start>=size: return self.motion_json({'error':'Range 越界'},416)
        self.send_response(206 if raw else 200)
        self.send_header('Content-Type',mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(end-start+1)); self.send_header('Accept-Ranges','bytes')
        if raw:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.end_headers()
        try:
            with path.open('rb') as f:
                f.seek(start); remaining=end-start+1
                while remaining:
                    b=f.read(min(256*1024,remaining))
                    if not b:break
                    self.wfile.write(b);remaining-=len(b)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass

    def motion_get(self):
        path=urlsplit(self.path).path
        try:
            if path in ('/motion-system.js','/motion-system.css'):
                return self.respond((ASSETS/path[1:]).read_bytes(), 'text/javascript; charset=utf-8' if path.endswith('.js') else 'text/css; charset=utf-8')
            if path=='/api/motions/session':return self.motion_json({'token':TOKEN})
            if path=='/api/motions/catalog':return self.motion_json(store.catalog())
            if path=='/api/motions/taxonomy':
                return self.motion_json(json.loads((ASSETS/'index-taxonomy.json').read_text('utf-8')))
            if path=='/api/motions/doctor':return self.motion_json(runtime.doctor())
            match=re.fullmatch(r'/api/motions/file/([a-f0-9]{32})/(preview\.png|video-with-audio\.mp4|task\.log|input\.json|plan\.json)',path)
            if match:
                store.get('job',match[1])
                return self.motion_file(store.root()/'instances'/match[1]/match[2])
            match=re.fullmatch(r'/api/motions/(preview|poster)/([a-f0-9]{32})',path)
            if match:
                item=store.get('item',match[2]);url=item.get('previewUrl')
                if not url:raise ValueError('来源未提供预览')
                _,env=runtime.environment()
                target=ensure_preview(url,env)
                with MEDIA_LOCK:
                    if match[1]=='poster':
                        poster=target.with_suffix('.jpg')
                        if not poster.is_file():
                            _,env=runtime.environment();ffmpeg=shutil.which('ffmpeg',path=env['PATH'])
                            if not ffmpeg: raise ValueError('本机未配置预览封面工具')
                            temporary=poster.with_suffix('.part.jpg')
                            try:
                                subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-ss','1','-i',str(target),'-frames:v','1','-vf','scale=640:640:force_original_aspect_ratio=decrease',str(temporary)],check=True,capture_output=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW if __import__('os').name=='nt' else 0)
                                temporary.replace(poster)
                            finally: temporary.unlink(missing_ok=True)
                        target=poster
                return self.motion_file(target)
            return self.motion_json({'error':'未找到 Motion 接口'},404)
        except (ValueError,OSError,KeyError,subprocess.SubprocessError) as exc:return self.motion_json({'error':str(exc)},400)

    def motion_post(self):
        try:
            origin=self.headers.get('Origin')
            if origin and origin != 'http://'+self.headers.get('Host',''):return self.motion_json({'error':'来源不匹配'},403)
            if not secrets.compare_digest(self.headers.get('X-Motion-Token',''),TOKEN):return self.motion_json({'error':'刷新页面后重试'},403)
            size=int(self.headers.get('Content-Length','0'))
            if urlsplit(self.path).path=='/api/motions/upload':
                ident=parse_qs(urlsplit(self.path).query).get('id',[''])[0];store.get('item',ident)
                if size<1 or size>MAX_PACKAGE:raise ValueError('上传文件大小无效')
                dest=store.root()/'incoming'/(store.uid()+'.motion');dest.parent.mkdir(parents=True,exist_ok=True)
                remaining=size
                with dest.open('xb') as f:
                    while remaining:
                        b=self.rfile.read(min(remaining,256*1024))
                        if not b:raise ValueError('上传中断')
                        f.write(b);remaining-=len(b)
                return self.motion_json(runtime.submit('import',ident,{'path':str(dest)}))
            if self.headers.get('Content-Type','').split(';')[0]!='application/json' or not 0<size<=2*1024*1024:
                raise ValueError('需要有效 JSON 请求')
            args=json.loads(self.rfile.read(size))
            if not isinstance(args,dict):raise ValueError('请求应为对象')
            return self.motion_json(dispatch(args))
        except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError) as exc:return self.motion_json({'error':str(exc)},400)
