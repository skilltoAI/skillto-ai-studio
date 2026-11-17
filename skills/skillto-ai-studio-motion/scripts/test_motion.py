import json
import os
import stat
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import motion_store as s
import motion_runtime as runtime
from motion_package import inspect_package, safe_name
from motion_network import check_url

class MotionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'SKILLTO_TABLE_ROOT':self.tmp.name});self.env.start()
    def tearDown(self):self.env.stop();self.tmp.cleanup()
    def add(self,**kw):return s.add({'title':'测试','sourceUrl':'https://motiongit.com/@test/example',**kw})
    def package(self,extra=None,manifest=None):
        p=Path(self.tmp.name)/'test.motion'
        m=manifest or {'format':'motiongit-template','specVersion':'0.1.0-draft.1','template':{'id':'test','version':'1.0'},'runtime':{'entry':'src/main.js','profile':'unknown/1'},'output':{'width':1080,'height':1920}}
        with zipfile.ZipFile(p,'w') as z:
            z.writestr('motion.json',json.dumps(m));z.writestr('src/main.js','example')
            for name,value in (extra or {}).items():z.writestr(name,value)
        return p
    def test_tags_rename_delete_preserve_other_data(self):
        i=self.add();a=s.tag_action('save',{'name':'A'});b=s.tag_action('save',{'name':'B'})
        s.update_item(i['id'],{'tagIds':[a['id'],b['id']],'rating':4})
        s.tag_action('save',{'id':a['id'],'name':'改名'})
        self.assertEqual(s.get('item',i['id'])['tagIds'],[a['id'],b['id']])
        s.tag_action('delete',{'id':a['id']});v=s.get('item',i['id'])
        self.assertEqual(v['tagIds'],[b['id']]);self.assertEqual(v['rating'],4);self.assertEqual(v['title'],'测试')
    def test_duplicate_tag(self):
        s.tag_action('save',{'name':'Motion'})
        with self.assertRaises(ValueError):s.tag_action('save',{'name':'motion'})
    def test_rating_not_run_count(self):
        i=self.add();r=s.update_item(i['id'],{'rating':5,'runCount':999})
        self.assertIsNone(r['runCount']);self.assertEqual(r['rating'],5)
        self.assertIsNone(s.update_item(i['id'],{'rating':None})['rating'])
        for accepted in (.5,1.5,2.5,4.5,5.0):
            self.assertEqual(s.update_item(i['id'],{'rating':accepted})['rating'],accepted)
        for v in (0,6,True,'5',2.2,float('nan'),float('inf')):
            with self.assertRaises(ValueError):s.update_item(i['id'],{'rating':v})
    def test_source_variant_dedupe(self):
        i=self.add(aspect='16:9');self.assertEqual(self.add(aspect='16:9')['id'],i['id'])
        self.assertNotEqual(self.add(aspect='9:16')['id'],i['id'])
    def test_view_defaults_and_preserves_manual_scores(self):
        i=self.add()
        self.assertFalse(i['viewed'])
        viewed=s.mark_viewed(i['id'])
        self.assertTrue(viewed['viewed'])
        self.assertEqual((viewed['rating'],viewed['ratingSource']),(1,'view-default'))
        self.assertEqual(s.mark_viewed(i['id'])['viewedAt'],viewed['viewedAt'])
        s.update_item(i['id'],{'rating':.5})
        self.assertEqual(s.mark_viewed(i['id'])['rating'],.5)
        self.assertEqual(s.get('item',i['id'])['ratingSource'],'manual')
        cleared=s.update_item(i['id'],{'rating':None})
        self.assertEqual((cleared['rating'],cleared['ratingSource']),(1,'view-default'))
        self.assertIsNone(cleared['runCount'])
        self.assertTrue(s.catalog()['items'][0]['viewed'])
    def test_legacy_view_does_not_infer_or_replace_rating(self):
        i=self.add();i.pop('viewed');i.pop('viewedAt');i.pop('ratingSource');i['rating']=3.5;s.write('item',i)
        self.assertFalse(s.catalog()['items'][0]['viewed'])
        viewed=s.mark_viewed(i['id'])
        self.assertEqual((viewed['rating'],viewed['ratingSource']),(3.5,'manual'))
    def test_missing_path_is_empty(self):
        i=self.add();i.update(localPath=str(Path(self.tmp.name)/'missing.motion'),renderable=True);s.write('item',i)
        self.assertEqual(s.catalog()['items'][0]['localPath'],'');self.assertFalse(s.catalog()['items'][0]['renderable'])
    def test_history_and_persistence(self):
        i=self.add();s.update_item(i['id'],{'favorite':True})
        with s.db() as con:self.assertGreaterEqual(con.execute('SELECT count(*) FROM history').fetchone()[0],2)
        self.assertTrue(s.get('item',i['id'])['favorite'])
    def test_unknown_tags_rejected(self):
        i=self.add()
        with self.assertRaises(ValueError):s.update_item(i['id'],{'tagIds':['missing']})
    def test_public_package_not_automatically_executable(self):
        p=self.package();dest=Path(self.tmp.name)/'extract';r=inspect_package(p,dest)
        self.assertEqual(r['status'],'verified');self.assertFalse(r['renderable']);self.assertTrue((dest/'src/main.js').is_file())
    def test_unsafe_paths(self):
        for n in ('../outside','/absolute','C:/bad','a\\b','a//b','a/./b','a./b','con.txt','a/NUL','a/../b'):
            with self.subTest(n=n),self.assertRaises(ValueError):safe_name(n)
    def test_case_collision(self):
        with self.assertRaises(ValueError):inspect_package(self.package({'SRC/main.js':'bad'}))
    def test_prefix_collision(self):
        with self.assertRaises(ValueError):inspect_package(self.package({'src':'bad'}))
    def test_symlink(self):
        p=self.package()
        with zipfile.ZipFile(p,'a') as z:
            info=zipfile.ZipInfo('link');info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(info,'outside')
        with self.assertRaises(ValueError):inspect_package(p)
    def test_missing_reference(self):
        m={'format':'motiongit-template','specVersion':'0.1.0-draft.1','template':{},'runtime':{'entry':'missing'},'output':{}}
        with self.assertRaises(ValueError):inspect_package(self.package(manifest=m))
    def test_personal_envelope_not_extracted(self):
        dest=Path(self.tmp.name)/'extract'
        r=inspect_package(self.package(manifest={'packageProfile':'personal-download-v1','specVersion':'1.0.0-rc.1'}),dest)
        self.assertEqual(r['status'],'unsupported');self.assertFalse(dest.exists())
    def test_unknown_version(self):
        m={'format':'motiongit-template','specVersion':'9.0','template':{},'runtime':{'entry':'src/main.js'},'output':{}}
        self.assertEqual(inspect_package(self.package(manifest=m))['status'],'unsupported')
    def test_bad_integrity(self):
        m={'format':'motiongit-template','specVersion':'0.1.0-draft.1','template':{},'runtime':{'entry':'src/main.js'},'output':{},'integrity':'integrity.json'}
        with self.assertRaises(ValueError):inspect_package(self.package({'integrity.json':json.dumps({'algorithm':'sha256','files':{'src/main.js':'0'*64}})},m))
    def test_network_restrictions(self):
        for u in ('http://localhost/a','https://127.0.0.1/a','https://motiontemplates.github.io.evil.test/a','https://motiontemplates.github.io/a?key=x','https://user@motiontemplates.github.io/a'):
            with self.assertRaises(ValueError):check_url(u)
        self.assertTrue(check_url('https://motiontemplates.github.io/385712/assets/demo.mp4'))
    def test_official_release_redirect_only(self):
        from motion_network import Redirects
        from urllib.request import Request
        official='https://github.com/motiontemplates/all/releases/download/batch/demo.mp4'
        signed='https://release-assets.githubusercontent.com/github-production-release-asset/demo?sig=public-temporary'
        self.assertEqual(check_url(official),official)
        for url in (signed,'https://github.com/other/repo/releases/download/batch/demo.mp4',official+'?key=x'):
            with self.assertRaises(ValueError):check_url(url)
        redirect=Redirects().redirect_request(Request(official),None,302,'Found',{},signed)
        self.assertEqual(redirect.full_url,signed)
        with self.assertRaises(ValueError):
            Redirects().redirect_request(Request('https://media.openaicut.com/demo.mp4'),None,302,'Found',{},signed)
        with self.assertRaises(ValueError):
            Redirects().redirect_request(Request(official),None,302,'Found',{},'http://release-assets.githubusercontent.com/demo?sig=x')
    def test_cancel_process(self):
        i=self.add();ident=s.uid();s.write('job',{'id':ident,'itemId':i['id'],'status':'running','stage':'test','kind':'render','createdAt':s.now()})
        outcome=[]
        def work():
            try:runtime.command(ident,[sys.executable,'-c','import time;time.sleep(30)'],self.tmp.name,Path(self.tmp.name)/'log',60)
            except InterruptedError:outcome.append('cancelled')
        t=threading.Thread(target=work);t.start()
        for _ in range(50):
            if ident in runtime.PROCESSES:break
            time.sleep(.1)
        proc=runtime.PROCESSES[ident];runtime.cancel(ident);t.join(10)
        self.assertFalse(t.is_alive());self.assertIsNotNone(proc.poll());self.assertEqual(outcome,['cancelled'])

if __name__=='__main__':unittest.main(verbosity=2)
