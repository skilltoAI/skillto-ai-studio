import json,os,sys,tempfile,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
import motion_index as m
class IndexTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'SKILLTO_TABLE_ROOT':self.tmp.name});self.env.start();self.repo=Path(self.tmp.name)/'source';self.repo.mkdir();subprocess.run(['git','init',str(self.repo)],capture_output=True,check=True)
  subprocess.run(['git','-C',str(self.repo),'-c','user.email=test@example.invalid','-c','user.name=Test','commit','--allow-empty','-m','fixture'],capture_output=True,check=True)
  self.raw={'format':'motiongit.catalog/1','templates':[{'repositoryId':'one','title':{'zh':'黑底数字滚动与对比表格'},'summary':{'zh':'计数增长'},'ratio':'16:9','additionalDemos':[{'repositoryId':'one','title':{'zh':'竖屏版'},'ratio':'9:16'}]}],'previews':[]};self.save()
 def save(self):(self.repo/'catalog.json').write_text(json.dumps(self.raw),'utf-8')
 def tearDown(self):self.env.stop();self.tmp.cleanup()
 def test_sync_preserves_personal_data_and_local_file(self):
  import motion_store as store
  m.build(self.repo);self.assertEqual(m.sync_library()['synced'],2)
  item=next(i for i in store.catalog()['items'] if i['indexId']=='one:16:9');store.update_item(item['id'],{'rating':5,'favorite':True,'title':'Personal title'})
  m.sync_library();saved=store.get('item',item['id']);self.assertEqual(saved['rating'],5);self.assertTrue(saved['favorite']);self.assertEqual(saved['title'],'Personal title');self.assertTrue(saved['sourceFacets']);self.assertEqual(len(store.catalog()['items']),2)
 def test_dry_run_and_atomic_rejection(self):
  import motion_store as store
  from motion_intake import ingest
  m.build(self.repo);batch=m.intake_batch();r=ingest(batch,True)
  self.assertEqual(r['created'],2);self.assertFalse(store.catalog()['items'])
  batch['items'][1]['labels']=[{'facet':'bad','value':'invented','evidence':'x','method':'human'}]
  with self.assertRaises(ValueError):ingest(batch)
  self.assertFalse(store.catalog()['items'])
 def test_sync_preserves_verified_package(self):
  import motion_store as store
  m.build(self.repo);m.sync_library();item=next(i for i in store.catalog()['items'] if i['indexId']=='one:16:9')
  package=Path(self.tmp.name)/'original.motion';package.write_bytes(b'original')
  item.update(localPath=str(package),version='verified-local',renderable=True,posterUrl='/local-render.png');store.write('item',item)
  again=m.sync_library();saved=store.get('item',item['id'])
  self.assertEqual(again['created'],0);self.assertEqual(saved['version'],'verified-local');self.assertTrue(saved['renderable']);self.assertEqual(saved['posterUrl'],'/local-render.png')
 def test_variants_and_refresh(self):
  m.build(self.repo);self.assertEqual(m.status()['documents'],2);m.build(self.repo);self.assertEqual(m.status()['documents'],2)
 def test_keyword_filter_and_evidence(self):
  m.build(self.repo);r=m.search('数字',{'background':['深色底']},'keyword');self.assertEqual(len(r),1);self.assertTrue(all(x['evidence'] for x in r[0]['labels']))
  self.assertFalse(m.search('数字',{'ratio':['9:16']},'keyword'))
 def test_manual_evidence_survives_refresh(self):
  m.build(self.repo);m.label('one:16:9','metric','Star数','人工核对输入字段');m.build(self.repo)
  self.assertTrue(m.search('数字',{'metric':['Star数']},'keyword'))
  m.label('one:16:9','background','深色底','人工纠正',True);m.build(self.repo);self.assertFalse(m.search('数字',{'background':['深色底']},'keyword'))
 def test_invalid_input_and_no_false_comparison(self):
  self.raw['templates'][0]['title']={'zh':'高对比海报'};self.raw['templates'][0]['summary']={'zh':''};self.save();m.build(self.repo)
  self.assertFalse(m.search('海报',{'grammar':['对比']},'keyword'))
  with self.assertRaises(ValueError):m.search('海报',{'bad':['value']},'keyword')
  with self.assertRaises(ValueError):m.label('one:16:9','metric','Star数','')
 def test_stale_vectors_not_used(self):
  m.build(self.repo);c=m.connect()
  with c:c.execute('INSERT INTO vectors VALUES (?,?,?,?)',('one:16:9','old','fixture',b'1234'))
  c.close();self.assertEqual(m.status()['vectorsCurrent'],0)
if __name__=='__main__':unittest.main(verbosity=2)
