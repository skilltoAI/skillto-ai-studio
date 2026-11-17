"""HTTP contract regression tests; isolated root, no production library mutations."""
import json
import os
import tempfile
import threading
import time
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch
import motion_store as store
import motion_runtime as runtime
from motion_http import MotionMixin

class Handler(MotionMixin, BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def respond(self,b,ctype,status=200):
        self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
    def do_GET(self):self.motion_get()
    def do_POST(self):self.motion_post()

class MotionHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{'SKILLTO_TABLE_ROOT':self.temp.name});self.env.start()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base='http://127.0.0.1:'+str(self.server.server_port)
        self.token=json.loads(self.fetch('/api/motions/session')[1])['token']
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.env.stop();self.temp.cleanup()
    def fetch(self,path,body=None,headers=None):
        try:r=urlopen(Request(self.base+path,data=body,headers=headers or {}),timeout=15)
        except HTTPError as e:r=e
        with r:return r.status,r.read(),dict(r.headers)
    def action(self,**args):
        code,body,_=self.fetch('/api/motions/action',json.dumps(args).encode(),{'Content-Type':'application/json','X-Motion-Token':self.token})
        self.assertEqual(code,200,body);return json.loads(body)
    def wait(self,ident):
        for _ in range(200):
            job=store.get('job',ident)
            if job['status'] not in ('queued','running','cancelling'):return job
            time.sleep(.05)
        self.fail('job did not terminate')
    def test_csrf_and_origin(self):
        for headers in ({'Content-Type':'application/json'},{'Content-Type':'application/json','X-Motion-Token':self.token,'Origin':'https://elsewhere.example'}):
            self.assertEqual(self.fetch('/api/motions/action',b'{"action":"seed"}',headers)[0],403)
        self.assertFalse(store.catalog()['items'])
    def test_tags_rating_and_refresh(self):
        item=self.action(action='seed');a=self.action(action='tag',name='A');b=self.action(action='tag',name='B')
        self.action(action='update',id=item['id'],tagIds=[a['id'],b['id']],rating=3.5,runCount=123)
        self.action(action='tag',id=a['id'],name='Renamed')
        self.action(action='tag',id=b['id'],operation='delete')
        saved=json.loads(self.fetch('/api/motions/catalog')[1])['items'][0]
        self.assertEqual(saved['tagIds'],[a['id']]);self.assertEqual(saved['rating'],3.5);self.assertIsNone(saved['runCount'])
        self.assertIsNone(self.action(action='update',id=item['id'],rating=None)['rating'])
    def test_upload_failure_retry_new_task(self):
        item=self.action(action='seed')
        code,body,_=self.fetch('/api/motions/upload?id='+item['id'],b'not a zip',{'X-Motion-Token':self.token})
        self.assertEqual(code,200);first=self.wait(json.loads(body)['id']);self.assertEqual(first['status'],'failed')
        retry=self.action(action='retry',id=first['id']);self.assertNotEqual(retry['id'],first['id']);self.assertEqual(self.wait(retry['id'])['status'],'failed')
        self.assertEqual(store.catalog()['items'][0]['localPath'],'')
    def test_view_and_default_rating_persist(self):
        item=self.action(action='seed')
        viewed=self.action(action='view',id=item['id'])
        self.assertEqual((viewed['viewed'],viewed['rating'],viewed['ratingSource']),(True,1,'view-default'))
        self.action(action='update',id=item['id'],rating=4.5)
        self.action(action='view',id=item['id'])
        saved=json.loads(self.fetch('/api/motions/catalog')[1])['items'][0]
        self.assertEqual((saved['viewed'],saved['rating'],saved['ratingSource']),(True,4.5,'manual'))
    def test_intake_dry_run_and_background_preview(self):
        batch={'format':'skillto.motion-intake/1','items':[{'id':'demo:16:9','title':'Demo','source':'MotionGit','sourceUrl':'https://motiongit.com/@test/demo','ratio':'16:9','demo':'https://motiontemplates.github.io/demo.mp4'}]}
        with patch('motion_media.ensure_preview',return_value=None) as prepare:
            dry=self.action(action='ingest',batch=batch,dryRun=True)
            self.assertNotIn('mediaJob',dry);self.assertFalse(store.all_objects('job'));prepare.assert_not_called()
            result=self.action(action='ingest',batch=batch)
            job=self.wait(result['mediaJob']['id'])
            self.assertEqual(job['status'],'succeeded')
            self.assertEqual(job['mediaResults'][0]['status'],'source-small')
            self.assertEqual(prepare.call_count,1)
    def test_large_preview_cache_and_range(self):
        item=self.action(action='seed')
        def fake_download(url,target,limit,cancel=lambda:False):
            self.assertGreaterEqual(limit,211887999)
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(b'0123456789')
        with patch('motion_media.download',side_effect=fake_download) as download:
            for _ in range(2):
                code,body,headers=self.fetch('/api/motions/preview/'+item['id'],headers={'Range':'bytes=2-5'})
                self.assertEqual((code,body,headers['Content-Range']),(206,b'2345','bytes 2-5/10'))
            self.assertEqual(download.call_count,1)
    def test_unknown_runtime_import_and_media_range(self):
        item=self.action(action='seed');p=Path(self.temp.name)/'example.motion'
        m={'format':'motiongit-template','specVersion':'0.1.0-draft.1','template':{'id':'test','version':'1'},'runtime':{'entry':'source.js','profile':'unknown/1'},'output':{'width':100,'height':100}}
        with zipfile.ZipFile(p,'w') as z:z.writestr('motion.json',json.dumps(m));z.writestr('source.js','not executed')
        job=self.action(action='import',id=item['id'],path=str(p));self.assertEqual(self.wait(job['id'])['status'],'succeeded')
        saved=store.catalog()['items'][0];self.assertTrue(Path(saved['localPath']).is_file());self.assertFalse(saved['renderable']);self.assertEqual(saved['aspect'],'1:1')
        work=store.root()/'instances'/job['id'];(work/'video-with-audio.mp4').write_bytes(b'0123456789')
        code,body,headers=self.fetch('/api/motions/file/'+job['id']+'/video-with-audio.mp4',headers={'Range':'bytes=2-5'})
        self.assertEqual((code,body,headers['Content-Range']),(206,b'2345','bytes 2-5/10'))
        self.assertEqual(self.fetch('/api/motions/file/'+job['id']+'/video-with-audio.mp4',headers={'Range':'bytes=99-'})[0],416)
        self.assertEqual(self.fetch('/api/motions/file/'+job['id']+'/../runtime.local.json')[0],404)
    def test_download_failure_recovery(self):
        item=self.action(action='add',title='Blocked origin',sourceUrl='https://example.com/template',downloadUrl='http://127.0.0.1/private')
        job=self.action(action='download',id=item['id']);self.assertEqual(self.wait(job['id'])['status'],'failed')
        self.assertFalse(store.catalog()['items'][0]['localPath'])
    def test_restart_recovery_preserves_output(self):
        item=self.action(action='seed');ident=store.uid();work=store.root()/'instances'/ident;work.mkdir(parents=True);output=work/'video-with-audio.mp4';output.write_bytes(b'keep')
        store.write('job',{'id':ident,'itemId':item['id'],'kind':'render','status':'running','stage':'test','createdAt':store.now(),'args':{}})
        runtime.recover();self.assertEqual(store.get('job',ident)['status'],'failed');self.assertEqual(output.read_bytes(),b'keep')

if __name__=='__main__':unittest.main(verbosity=2)
