from __future__ import annotations
import importlib.util,sys
import json
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse, unquote
PROJECT_ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(PROJECT_ROOT.parent/'scrapling'))
from douyin_tracker import review_web
report_skill=Path(__file__).resolve().parents[1]
skill=report_skill
sys.path.insert(0,str(report_skill/'scripts'))
import report_system
import rewrite_system
import rewrite_voice
# Optional sibling capability; installed clients keep their own skill root.
workbench_scripts = report_skill.parent / "skillto-ai-studio-workbench" / "scripts"
if workbench_scripts.is_dir():
 sys.path.insert(0, str(workbench_scripts))
 from workbench import WorkbenchMixin
else:
 class WorkbenchMixin: pass
motion_scripts = report_skill.parent / 'skillto-ai-studio-motion' / 'scripts'
if motion_scripts.is_dir():
 sys.path.insert(0, str(motion_scripts))
 from motion_http import MotionMixin
 import motion_runtime
 motion_runtime.recover()
else:
 class MotionMixin: pass
spec=importlib.util.spec_from_file_location('review_store',skill/'scripts/server.py');store=importlib.util.module_from_spec(spec);spec.loader.exec_module(store)
review_web.table_store=lambda:store
rewrite_system.TABLE_STORE = store
RESEARCH_ROOT=(PROJECT_ROOT/'research').resolve()
RESEARCH_MIME={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg',
               '.webp':'image/webp','.gif':'image/gif','.md':'text/plain; charset=utf-8',
               '.mp4':'video/mp4'}
def research_asset_path(url_path):
 prefix='/assets/research/'
 if not url_path.startswith(prefix):
  raise ValueError('Unsupported asset path')
 relative=unquote(url_path[len(prefix):])
 if not relative or any(c in relative for c in ('\\', ':', '\x00')):
  raise ValueError('Invalid asset path')
 path=(RESEARCH_ROOT/relative).resolve()
 if not path.is_relative_to(RESEARCH_ROOT) or path.suffix.lower() not in RESEARCH_MIME:
  raise ValueError('Invalid asset path')
 return path
class Handler(MotionMixin, WorkbenchMixin, review_web.ReviewHandler):
 def wb_send(self, data, content_type='application/json; charset=utf-8', status=200):
  if isinstance(data, bytes) and 'text/html' in content_type:
   return self.respond(data,content_type,status)
  return super().wb_send(data,content_type,status)
 def respond(self, data, content_type, status=200, attachment=None):
  if 'text/html' in content_type:
   text=data.decode('utf-8')
   extra='<link rel="stylesheet" href="/studio-theme.css"><script src="/studio-shell.js" defer></script>'
   if motion_scripts.is_dir():
    extra+='<link rel="stylesheet" href="/motion-system.css"><script src="/motion-system.js" defer></script>'
   if '/workspace-nav.js' not in text:
    extra+='<link rel="stylesheet" href="/workspace-nav.css"><script src="/workspace-nav.js" defer></script>'
   if '</head>' in text: text=text.replace('</head>',extra+'</head>',1)
   else: text=text.replace('<main>',extra+'<main>',1)
   data=text.encode('utf-8')
  return super().respond(data,content_type,status,attachment)

 def send_header(self,keyword,value):
  if keyword.lower()=='content-security-policy':
   metabase='http://127.0.0.1:3330'
   value=("default-src 'self'; img-src 'self' https: data: "+metabase+
          "; media-src 'self'; connect-src 'self' "+metabase+
          "; script-src 'self' "+metabase+
          "; style-src 'self' 'unsafe-inline' "+metabase+
          "; font-src 'self' data: "+metabase+
          "; frame-src 'self' "+metabase+"; worker-src 'self' blob:")
  super().send_header(keyword,value)
 def do_GET(self):
  path=urlparse(self.path).path
  if motion_scripts.is_dir() and (path.startswith('/api/motions/') or path in ('/motion-system.js','/motion-system.css')):
   return self.motion_get()
  if path in ('/studio-theme.css','/studio-shell.js','/studio-wordmark.png'):
   asset=report_skill/'assets'/('brand/studio-wordmark.png' if path.endswith('.png') else path[1:])
   return self.respond(asset.read_bytes(), 'image/png' if path.endswith('.png') else ('text/javascript' if path.endswith('.js') else 'text/css'))
  if path == '/breakdowns' or path.startswith('/workbench') or path.startswith('/api/workbench/'):
   return super().do_GET()
  if path.startswith('/assets/research/'):
   try:
    asset=research_asset_path(path)
    if not asset.is_file():
     self.respond_json({'error':'Image or research document not found'},404)
    elif asset.suffix.lower()=='.mp4' and hasattr(self,'motion_file'):
     self.motion_file(asset)
    else:
     self.respond(asset.read_bytes(),RESEARCH_MIME[asset.suffix.lower()])
   except (ValueError,OSError):
    self.respond_json({'error':'Invalid research asset path'},404)
  elif path.startswith('/assets/rewrite-audio/'):
   try:
    asset=rewrite_voice.audio_path(unquote(path.removeprefix('/assets/rewrite-audio/')))
    if not asset.is_file():
     self.respond_json({'error':'Audio not found'},404)
    else:
     size=asset.stat().st_size
     start,end=0,size-1
     range_header=self.headers.get('Range','')
     if range_header:
      import re
      match=re.fullmatch(r'bytes=(\d+)-(\d*)',range_header)
      if not match:raise ValueError('Invalid byte range')
      start=int(match.group(1))
      end=min(int(match.group(2)),size-1) if match.group(2) else size-1
      if start>=size or end<start:raise ValueError('Invalid byte range')
     self.send_response(206 if range_header else 200)
     self.send_header('Content-Type','audio/wav')
     self.send_header('Accept-Ranges','bytes')
     self.send_header('Content-Length',str(end-start+1))
     if range_header:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
     self.end_headers()
     with asset.open('rb') as handle:
      handle.seek(start)
      remaining=end-start+1
      while remaining:
       chunk=handle.read(min(1048576,remaining))
       if not chunk:break
       self.wfile.write(chunk)
       remaining-=len(chunk)
   except (rewrite_system.RewriteError,ValueError,OSError):
    self.respond_json({'error':'Invalid audio asset'},404)
  elif path.startswith('/assets/rewrite-case/'):
   name=path.removeprefix('/assets/rewrite-case/')
   assets={f'slide-{i}.png':(PROJECT_ROOT/'work'/f'note_7694608697625416674_slide_{i}.png','image/png') for i in range(1,5)}
   assets.update({f'7700790158655753507/contact-{i:02d}.png':(PROJECT_ROOT/'work'/'video_7700790158655753507'/f'contact_{i:02d}.png','image/png') for i in range(1,4)})
   assets['7700790158655753507/transcript.txt']=(PROJECT_ROOT/'work'/'video_7700790158655753507'/'transcript.txt','text/plain; charset=utf-8')
   scene_root=PROJECT_ROOT/'work'/'video_7705653137557818639'
   assets['7705653137557818639/transcript.txt']=(scene_root/'transcript.txt','text/plain; charset=utf-8')
   for stem in ('source','7705090498729479439','7704669356004822281','7703488914518184825','7703519702576448433'):
    assets[f'7705653137557818639/{stem}_contact_3x3.jpg']=(scene_root/f'{stem}_contact_3x3.jpg','image/jpeg')
   for number in range(1,4):
    sheet_name=f'xiaotianle_interview_contact_{number:02d}_3x3.jpg'
    assets[f'7705653137557818639/{sheet_name}']=(scene_root/sheet_name,'image/jpeg')
   assets['7705653137557818639/xiaotianle_article_photos_contact_3x3.jpg']=(scene_root/'xiaotianle_article_photos_contact_3x3.jpg','image/jpeg')
   assets['7705653137557818639/xiaotianle_suzhou_daily_contact_3x3.jpg']=(scene_root/'xiaotianle_suzhou_daily_contact_3x3.jpg','image/jpeg')
   asset_info=assets.get(name)
   if asset_info and asset_info[0].is_file():self.respond(asset_info[0].read_bytes(),asset_info[1])
   else:self.respond_json({'error':'Asset not found'},404)
  elif path in ['/schema-controls.js','/schema-controls.css','/table-lineage.js','/table-lineage.css','/workspace-nav.js','/workspace-nav.css','/report-system.js','/report-system.css','/rewrite-system.js','/rewrite-system.css']:
   source=(report_skill/'assets'/path[1:]) if (report_skill/'assets'/path[1:]).is_file() else (skill/'assets'/path[1:])
   self.respond(source.read_bytes(),'text/javascript' if path.endswith('.js') else 'text/css')
  elif path=='/api/reports/catalog':
   try:self.respond_json(report_system.catalog())
   except report_system.ReportError as exc:self.respond_json({'error':str(exc)},exc.status)
  elif path=='/api/rewrites/voice-status':
   params=__import__('urllib.parse').parse.parse_qs(urlparse(self.path).query)
   self.respond_json(rewrite_voice.status(params.get('job',[''])[0],params.get('id',[''])[0],params.get('versionId',[''])[0]))
  elif path=='/api/rewrites':
   self.respond_json(rewrite_system.dispatch({'action':'list'}))
  elif path=='/api/reports/lineage':
   self.respond_json(report_system.lineage())
  elif path=='/api/reports/item':
   try:self.respond_json(report_system.get_report(__import__('urllib.parse').parse.parse_qs(urlparse(self.path).query)['id'][0]))
   except (report_system.ReportError,KeyError,IndexError) as exc:self.respond_json({'error':str(exc)},getattr(exc,'status',400))
  elif path=='/api/reports/embed':
   try:self.respond_json(report_system.embed(__import__('urllib.parse').parse.parse_qs(urlparse(self.path).query)['id'][0]))
   except (report_system.ReportError,KeyError,IndexError) as exc:self.respond_json({'error':str(exc)},getattr(exc,'status',400))
  elif path=='/research-adapter.js':
   self.respond((PROJECT_ROOT/'runtime'/'pet_refresh_20261028'/'research-adapter.js').read_bytes(),'text/javascript; charset=utf-8')
  elif path=='/app.js':
   text=(review_web.ASSETS/'app.js').read_text(encoding='utf-8').replace('在抖音播放','在 TikTok 打开原视频').replace('抖音原视频','原视频').replace('账号','记录')
   self.respond(text.encode(),'text/javascript; charset=utf-8')
  elif path=='/':
   text=(review_web.ASSETS/'index.html').read_text(encoding='utf-8')
   text=text.replace('</head>','<link rel="stylesheet" href="/schema-controls.css"><link rel="stylesheet" href="/table-lineage.css"><link rel="stylesheet" href="/workspace-nav.css"><link rel="stylesheet" href="/report-system.css"><link rel="stylesheet" href="/rewrite-system.css"><script src="/schema-controls.js" defer></script><script src="/table-lineage.js" defer></script><script src="/workspace-nav.js" defer></script><script src="/report-system.js" defer></script><script src="/rewrite-system.js" defer></script><script src="/research-adapter.js" defer></script><style>#rowForm textarea{width:100%;min-height:70px}#rowDialog{max-width:760px;width:90vw}#rowForm{max-height:70vh;overflow:auto}#minVideos,#dateFrom,#dateTo{display:none}.filters label:has(#minVideos),.filters label:has(#dateFrom),.filters label:has(#dateTo){display:none}</style></head>')
   text=text.replace('抖音账号表','TikTok 内容研究表').replace('抖音账号','TikTok 内容研究').replace('添加账号','添加记录').replace('搜索账号或视频','搜索关键词、创作者或视频')
   text=text.replace('从本地追踪库同步','重新读取本地报表').replace('↻ <span>同步</span>','↻ <span>刷新</span>')
   self.respond(text.encode(),'text/html; charset=utf-8')
  else:super().do_GET()
 def do_POST(self):
  if motion_scripts.is_dir() and urlparse(self.path).path.startswith('/api/motions/'):
   return self.motion_post()
  if urlparse(self.path).path.startswith('/api/workbench/'):
   return super().do_POST()
  if self.path=='/api/rewrites/voice':
   try:
    if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise rewrite_system.RewriteError('Expected JSON')
    size=int(self.headers.get('Content-Length','0'))
    if size<1 or size>4096:raise rewrite_system.RewriteError('Request size is invalid')
    args=json.loads(self.rfile.read(size))
    self.respond_json(rewrite_voice.start(args.get('id',''),args.get('versionId','')))
   except (rewrite_system.RewriteError,ValueError,KeyError,TypeError,OSError) as exc:self.respond_json({'error':str(exc)},400)
  elif self.path=='/api/rewrites':
   try:
    if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise rewrite_system.RewriteError('Expected JSON')
    size=int(self.headers.get('Content-Length','0'))
    if size<1 or size>1000000:raise rewrite_system.RewriteError('Request size is invalid')
    self.respond_json(rewrite_system.dispatch(json.loads(self.rfile.read(size))))
   except (rewrite_system.RewriteError,ValueError,KeyError,TypeError) as exc:self.respond_json({'error':str(exc)},400)
  elif self.path=='/api/reports':
   try:
    if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise report_system.ReportError('Expected JSON')
    size=int(self.headers.get('Content-Length','0'))
    if size<1 or size>1000000:raise report_system.ReportError('Request size is invalid')
    self.respond_json(report_system.dispatch(json.loads(self.rfile.read(size))))
   except report_system.ReportError as exc:self.respond_json({'error':str(exc)},exc.status)
   except (ValueError,KeyError,TypeError) as exc:self.respond_json({'error':str(exc)},400)
  elif self.path=='/api/reports/refresh':
   try:
    import subprocess
    task=report_skill/'reporting'/'sync_data.py'
    run=subprocess.run([sys.executable,'-B',str(task)],capture_output=True,text=True,timeout=120)
    if run.returncode:self.respond_json({'error':run.stderr[-1000:]},500)
    else:self.respond_json({'message':run.stdout.strip()})
   except Exception as exc:self.respond_json({'error':str(exc)},500)
  elif self.path=='/api/sync':self.respond_json({'tableId':None,'added':0,'updated':0})
  elif self.path=='/api/lineage':
   try:
    if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('Expected JSON')
    size=int(self.headers.get('Content-Length','0'))
    if size<1 or size>100000:raise ValueError('Request size is invalid')
    self.respond_json(store.table_lineage(__import__('json').loads(self.rfile.read(size))))
   except (ValueError,KeyError,TypeError) as exc:self.respond_json({'error':str(exc)},400)
  else:super().do_POST()
 def log_message(self,*args):pass
if __name__=='__main__':
 server=ThreadingHTTPServer(('127.0.0.1',8880),Handler)
 print('TikTok research tables: http://127.0.0.1:8880',flush=True)
 server.serve_forever()
