import json, os, sys, tempfile, threading, subprocess, time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from browser_profiles import BrowserProfiles
from playwright.sync_api import sync_playwright
class Fixture(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(b'<title>Fixture</title><input aria-label="Message"><button>Save</button><output></output><script>document.querySelector("button").onclick=()=>document.querySelector("output").textContent=document.querySelector("input").value</script>')
 def log_message(self,*a):pass
fixture=ThreadingHTTPServer(('127.0.0.1',0),Fixture)
threading.Thread(target=fixture.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{fixture.server_port}'
with tempfile.TemporaryDirectory(prefix='skillto-browser-') as root:
 manager=BrowserProfiles(root)
 a=manager.call({'action':'create','name':'用户甲'})['id'];b=manager.call({'action':'create','name':'用户乙'})['id']
 def call(action,user=a,**kw):return manager.call(dict(action=action,userId=user,**kw))
 try:
  call('launch');call('navigate',url=url)
  call('evaluate',expression="document.cookie='identity=A; max-age=3600; path=/';localStorage.setItem('identity','A')")
  call('launch',b);call('navigate',b,url=url)
  assert call('evaluate',b,expression="[document.cookie,localStorage.getItem('identity')]")['value']==['',None]
  call('fill',selector='input',text='AI control works');call('click',selector='button')
  assert call('evaluate',expression="document.querySelector('output').textContent")['value']=='AI control works'
  page=call('pages')['pages'][0]['pageId']
  try:call('snapshot',b,pageId=page);raise AssertionError('cross-user page accepted')
  except ValueError:pass
  assert len(call('screenshot')['base64'])>100
  call('close');call('rename',name='用户甲改名');call('launch');call('navigate',url=url)
  assert call('evaluate',expression="[document.cookie,localStorage.getItem('identity')]")['value']==['identity=A','A']
  call('close');call('close',b)
 finally:manager.close()
 manager=BrowserProfiles(root)
 try:
  assert manager.call({'action':'list'})['users'][0]['name']=='用户甲改名'
  manager.call({'action':'launch','userId':a});manager.call({'action':'navigate','userId':a,'url':url})
  assert manager.call({'action':'evaluate','userId':a,'expression':"localStorage.getItem('identity')"})['value']=='A'
  manager.call({'action':'close','userId':a})
  try:manager.call({'action':'delete','userId':a,'confirmName':'wrong'});raise AssertionError('bad confirmation accepted')
  except ValueError:pass
  manager.call({'action':'delete','userId':a,'confirmName':'用户甲改名'})
  assert list((Path(root)/'browser-profiles/trash').iterdir())
 finally:manager.close()
print('PASS real Chrome: username CRUD, cookie/storage isolation, rename, browser+service restart persistence, input/click, page ownership, screenshot, recoverable deletion')
fixture.shutdown()
