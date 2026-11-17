import json,tempfile,threading,sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from browser_profiles import BrowserProfiles
ready=threading.Event()
class Fixture(BaseHTTPRequestHandler):
 def do_GET(self):
  if self.path=='/ready':ready.set()
  if self.path=='/parent':body='<meta charset="utf-8"><title>弹窗测试</title><a id="new" href="/child" target="_blank" title="打开中文页面">打开新窗口</a><script>setTimeout(()=>document.getElementById("new").click(),600)</script>'
  else:body='<meta charset="utf-8"><title>中文新窗口</title><h1>中文显示正常</h1><script>fetch("/ready")</script>'
  self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(body.encode())
 def log_message(self,*a):pass
server=ThreadingHTTPServer(('127.0.0.1',0),Fixture);threading.Thread(target=server.serve_forever,daemon=True).start()
with tempfile.TemporaryDirectory(prefix='skillto-popup-') as root:
 m=BrowserProfiles(root)
 try:
  uid=m.call({'action':'create','name':'弹窗验证'})['id']
  m.call({'action':'launch','userId':uid})
  m.call({'action':'navigate','userId':uid,'url':f'http://127.0.0.1:{server.server_port}/parent'})
  # NO HTTP/MCP/manager calls here: human-created popup must load while idle.
  assert ready.wait(8),'New target stayed paused while service was idle'
  import time
  deadline=time.monotonic()+4
  while len(m.pages)<2 and time.monotonic()<deadline:time.sleep(.05)
  assert len(m.pages)==2, 'Popup event not dispatched while idle'
  pages=m.call({'action':'pages','userId':uid})['pages'];assert len(pages)==2
  child=next(p for p in pages if p['url'].endswith('/child'))
  value=m.call({'action':'evaluate','userId':uid,'pageId':child['pageId'],'expression':'({title:document.title,charset:document.characterSet,lang:navigator.language,heading:document.querySelector("h1").textContent})'})['value']
  assert value['title']=='中文新窗口' and value['heading']=='中文显示正常' and value['charset']=='UTF-8'
  print('PASS: target=_blank popup loaded during complete MCP/API idle; Chinese DOM/title UTF-8 correct')
 finally:m.close()
server.shutdown()
