import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import ai_asset_library as assets
import ai_asset_media as media


class AssetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = SimpleNamespace(ROOT=Path(self.temp.name), locked=contextlib.nullcontext,
            read_json=lambda p: json.loads(p.read_text()),
            write_json=lambda p,d: p.write_text(json.dumps(d)),
            event=lambda action,before,after: {'action':action,'before':before,'after':after})
        self.batch = {'action':'ingest','source':{'url':'https://my.feishu.cn/wiki/Example1','title':'Example','access':'anonymous','checkedAt':'2026-11-19'},
            'items':[{'library':'red-white','sourceBlockId':'Block1','title':'Test <action>','prompt':'Line 1\nLine 2',
                      'filename':'example.mp4','fileToken':'PublicFile1','mediaDigest':'a'*64,'playback':'source-page'}]}

    def test_bad_local_upload_never_enters_catalog(self):
        def action(name, **args):
            return assets.dispatch({'action': name, **args}, self.store)

        topic = action('create_topic', title='本机专题')['topic']
        upload = {'topicId': topic['id'], 'itemKey': 'clip-1', 'title': '本机片段',
                  'filename': 'clip.mp4', 'size': 12, 'sha256': 'a' * 64}
        with self.assertRaises(ValueError):
            action('begin_upload', **{**upload, 'filename': '../clip.mp4'})
        key = action('begin_upload', **upload)['uploadId']
        with self.assertRaises(ValueError):
            action('upload_chunk', uploadId=key, offset=1, base64='AAAA')
        action('upload_chunk', uploadId=key, offset=0, base64='AAAAAGZ0eXBpc29t')
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            action('finish_upload', uploadId=key)
        self.assertEqual(action('catalog')['items'], [])
        self.assertTrue(action('abort_upload', uploadId=key)['aborted'])
        self.assertEqual(list((self.store.ROOT / 'ai-asset-media').iterdir()), [])

    def tearDown(self):
        self.temp.cleanup()

    def test_atomic_idempotent_metadata_only_and_duplicate_attribution(self):
        assets.dispatch({**self.batch,'dryRun':True},self.store)
        self.assertFalse((self.store.ROOT/'ai-assets.json').exists())
        assets.dispatch(self.batch,self.store)
        self.assertFalse(assets.dispatch(self.batch,self.store)['changed'])
        other = {**self.batch,'source':{**self.batch['source'],'url':'https://my.feishu.cn/wiki/Example2'}}
        assets.dispatch(other,self.store)
        data = assets.dispatch({},self.store)
        self.assertEqual(len(data['items']),1)
        self.assertEqual(len(data['items'][0]['references']),2)
        self.assertEqual(data['items'][0]['prompt'],'Line 1\nLine 2')
        self.assertEqual([p.name for p in self.store.ROOT.iterdir()],['ai-assets.json'])
        before=(self.store.ROOT/'ai-assets.json').read_bytes()
        for url in ('http://localhost/x','https://evil.test/wiki/X','https://my.feishu.cn/wiki/A?secret=x'):
            with self.assertRaises(ValueError):
                assets.dispatch({**self.batch,'source':{**self.batch['source'],'url':url}},self.store)
        with self.assertRaises(ValueError):
            assets.dispatch({**self.batch,'items':self.batch['items']+[{'library':'invalid'}]},self.store)
        self.assertEqual((self.store.ROOT/'ai-assets.json').read_bytes(),before)

    def test_stream_is_bounded_and_closed_without_files(self):
        response=io.BytesIO(b'video'*50000)
        self.assertEqual(sum(map(len,media.stream_chunks(response))),250000)
        self.assertTrue(response.closed)
        self.assertEqual(list(self.store.ROOT.iterdir()),[])
        with patch.object(media,'MAX_MEDIA',10), self.assertRaises(ValueError):
            list(media.stream_chunks(io.BytesIO(b'video'*100)))

    def test_media_range_and_type_checks(self):
        item={'fileToken':'PublicFile1','sourceUrl':'https://my.feishu.cn/wiki/Example1#Block1'}
        with self.assertRaises(ValueError):media.open_media(item,'bytes=0-4,8-12')
        response=SimpleNamespace(status=200,headers={'Content-Type':'text/html'},close=lambda:None)
        with patch.object(media,'anonymous_headers',return_value={}), patch.object(media.urllib.request,'build_opener') as opener:
            opener.return_value.open.return_value=response
            with self.assertRaisesRegex(ValueError,'可播放视频'):media.open_media(item)


if __name__=='__main__': unittest.main()
