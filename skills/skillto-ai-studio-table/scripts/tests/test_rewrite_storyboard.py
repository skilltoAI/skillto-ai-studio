from test_rewrite_analysis import AnalysisTests,store
import unittest
class StoryboardTests(AnalysisTests):
 def save_board(self,rows,revision=0,key='openingStoryboard'):
  return store.dispatch(dict(action='save_storyboard',id=self.item['id'],storyboardKey=key,rows=rows,expectedRevision=revision))
 def test_storyboard_roundtrip_and_form_protection(self):
  row=dict(id='s1',title='S1',feedback='',frames=[dict(url='/assets/research/a.png',label='首帧')],narration='你身边',animation='卡词')
  saved=self.save_board([row]);self.assertEqual(saved['openingStoryboard']['revision'],1)
  self.assertEqual(saved['openingStoryboard']['rows'][0]['feedback'],'')
  saved=self.save_board([row],1);self.assertEqual(len(saved['history']),1)
  updated=store.dispatch(dict(action='update',id=self.item['id'],manuscript=self.item))
  self.assertEqual(updated['openingStoryboard'],saved['openingStoryboard'])
  self.assertEqual(updated['transcriptVersions'],self.item['transcriptVersions'])
  self.assertEqual(updated['fullStoryboard']['rows'],[])
  row['feedback']='动画慢一点\n箭头更细';saved=self.save_board([row],1)
  self.assertEqual(store.read()['manuscripts'][0]['openingStoryboard']['rows'][0]['feedback'],row['feedback'])
  self.assertEqual(saved['history'][-1]['before']['rows'][0]['feedback'],'')
 def test_storyboard_rejects_conflict_and_unsafe_media(self):
  good=dict(id='s',frames=[]);self.save_board([good]);before=store.FILE.read_bytes()
  cases=[([good],0),([dict(id='s',frames=[dict(url='javascript:alert(1)')])],1),([dict(id='s',frames=[dict(url='/assets/a')]*5)],1),([good,good],1)]
  for rows,rev in cases:
   with self.assertRaises(store.RewriteError):self.save_board(rows,rev)
   self.assertEqual(before,store.FILE.read_bytes())
 def test_opening_versions_keep_old_feedback_and_independent_edits(self):
  row=dict(id='s1',feedback='人工意见',frames=[])
  m=self.save_board([row]);b=m['openingStoryboard']
  m=store.dispatch(dict(action='create_storyboard_version',id=self.item['id'],expectedRevision=b['revision'],label='V2 修改'))
  b=m['openingStoryboard'];self.assertEqual(b['activeVersionId'],'v2')
  row['feedback']='';row['title']='新镜头';m=self.save_board([row],b['revision'])
  b=m['openingStoryboard'];self.assertEqual(b['versions'][0]['rows'][0]['feedback'],'人工意见')
  m=store.dispatch(dict(action='select_storyboard_version',id=self.item['id'],expectedRevision=b['revision'],versionId='v1'))
  self.assertEqual(m['openingStoryboard']['rows'][0]['feedback'],'人工意见')
  b=m['openingStoryboard'];m=store.dispatch(dict(action='rename_storyboard_version',id=self.item['id'],expectedRevision=b['revision'],versionId='v2',label='3段12秒'))
  self.assertEqual(m['openingStoryboard']['versions'][1]['label'],'3段12秒')
  with self.assertRaises(store.RewriteError):store.dispatch(dict(action='select_storyboard_version',id=self.item['id'],expectedRevision=b['revision'],versionId='v2'))
  self.assertEqual(store.read()['manuscripts'][0]['openingStoryboard']['activeVersionId'],'v1')
if __name__=='__main__':unittest.main()
