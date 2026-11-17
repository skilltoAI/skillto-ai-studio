"""Offline persistence, HTTP auth/range and real local MP4/HLS/DASH tests."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch
import workbench as app
import download_worker as worker
from dependencies import ffmpeg_path

class WorkerDiagnosticTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('yt_dlp'), 'Install yt-dlp for extractor matching')
    def test_douyin_modal_is_supported_without_altering_media_signatures(self):
        from yt_dlp.extractor.tiktok import DouyinIE
        for url in ['https://www.douyin.com/?modal_id=123456',
                    'https://www.douyin.com/user/person?modal_id=123456',
                    'https://www.douyin.com/video/999?modal_id=123456',
                    'https://douyin.com/?vid=123456']:
            normalized = worker.page_url(url)
            self.assertEqual(normalized, 'https://www.douyin.com/video/123456')
            self.assertTrue(DouyinIE.suitable(normalized))
        for url in ['https://cdn.douyinvod.com/video/tos/a?sign=secret&vid=123456',
                    'https://douyin.com.evil.example/?modal_id=123456',
                    'https://www.douyin.com/?modal_id=invalid',
                    'https://www.douyin.com/video/123456']:
            self.assertEqual(worker.page_url(url), url)

    def test_failure_categories_never_expose_upstream_text(self):
        cases = [('Fresh cookies (not necessarily logged in) are needed', '新鲜 Cookie'),
                 ('HTTP Error 403: Forbidden', '401/403'),
                 ('HTTP Error 429: Too Many Requests', '限流'),
                 ('Unsupported URL', '详情页'), ('Login required', '人工验证'),
                 ('ffmpeg merge failed', '合并失败'), ('timed out', '超时'),
                 ('unknown upstream error', '下载失败')]
        for text, expected in cases:
            message = worker.failure_message(Exception(text+' https://cdn.example/?token=SECRET Cookie: PRIVATE'))
            self.assertIn(expected, message)
            self.assertNotIn('SECRET', message)
            self.assertNotIn('PRIVATE', message)
            self.assertNotIn('https://', message)

class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ws = app.Workspace(self.temp.name)
        self.patch = patch.object(app, 'workspace', return_value=self.ws); self.patch.start()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.ws.close(); self.patch.stop(); self.temp.cleanup()

    def record(self):
        row = {'id':'sample', 'title':'样片', 'sourceUrl':'https://www.youtube.com/watch?v=sample',
               'status':'ready', 'notes':'', 'shots':[], 'history':[], 'revision':0, 'file':'video.mp4'}
        self.ws.save(row)
        folder = self.ws.root / 'media' / 'sample'; folder.mkdir(parents=True)
        (folder / 'video.mp4').write_bytes(b'0123456789')
        return row

    def request(self, path, data=None, headers=None):
        headers = headers or {}
        if data is not None: headers['Content-Type'] = 'application/json'
        return urlopen(Request(self.url+path, json.dumps(data).encode() if data is not None else None, headers), timeout=5)

    def test_persistence_history_conflict_and_nonfinite_shots(self):
        self.record()
        args = {'id':'sample','revision':0,'notes':'开场分析','shots':[{'start':0,'end':2.5,'text':'钩子'}]}
        row = self.ws.patch(args)
        self.assertEqual(row['revision'], 1); self.assertEqual(row['history'][0]['notes'], '')
        with self.assertRaises(ValueError): self.ws.patch(args)
        for start, end in [(float('nan'),2), (0,float('inf')), (True,3), (4,2)]:
            with self.assertRaises(ValueError): self.ws.patch({'id':'sample','revision':1,'shots':[{'start':start,'end':end}]})
        with self.assertRaises(ValueError): app.Workspace(self.temp.name)
        self.ws.close()
        other = app.Workspace(self.temp.name)
        self.assertEqual(other.get('sample')['notes'], '开场分析'); other.close()

    def test_source_keeps_video_id_without_tokens(self):
        self.assertEqual(app.safe_source('https://www.youtube.com/watch?v=abc&token=secret'), 'https://www.youtube.com/watch?v=abc')
        self.assertEqual(app.safe_source('https://www.xiaohongshu.com/explore/abc?xsec_token=secret'), 'https://www.xiaohongshu.com/explore/abc')

    def test_http_resources_auth_ranges_and_root(self):
        self.record()
        for path in ['/breakdowns','/workbench.js','/workbench.css','/workbench-logo.png','/workbench-install','/workbench-install.js','/api/workbench/extension-info','/']:
            with self.request(path) as response: self.assertEqual(response.status,200)
        for path in ['/api/workbench/records','/api/workbench/pairing','/api/workbench/media?id=sample']:
            with self.assertRaises(HTTPError) as error:
                self.request(path,headers={'Origin':'https://evil.example','Sec-Fetch-Site':'cross-site'})
            self.assertEqual(error.exception.code,403)
        with self.request('/api/workbench/records', headers={'Origin':'chrome-extension://abc','Authorization':'Bearer '+self.ws.token}) as response:
            self.assertEqual(len(json.load(response)['records']),1)
        with self.assertRaises(HTTPError): self.request('/api/workbench/pairing',headers={'Origin':'chrome-extension://abc','Authorization':'Bearer '+self.ws.token})
        with self.assertRaises(HTTPError): self.request('/api/workbench/extension-info',headers={'Origin':'https://evil.example','Sec-Fetch-Site':'cross-site'})
        with self.assertRaises(HTTPError): self.request('/api/workbench/extension-setup',data={},headers={'Origin':'https://evil.example','Sec-Fetch-Site':'cross-site'})
        with patch('extension_setup.open_setup') as opener:
            with self.request('/api/workbench/extension-setup',data={}) as response: self.assertTrue(json.load(response)['ok'])
            opener.assert_called_once_with(app.ASSETS / 'extension')
        for header, expected in [('bytes=2-5',b'2345'),('bytes=-3',b'789')]:
            with self.request('/api/workbench/media?id=sample',headers={'Range':header}) as response:
                self.assertEqual(response.status,206); self.assertEqual(response.read(),expected)
        with self.assertRaises(HTTPError) as error: self.request('/api/workbench/media?id=sample',headers={'Range':'bytes=20-30'})
        self.assertEqual(error.exception.code,416)

    def test_reject_local_urls_and_missing_authorization(self):
        for url in ['http://127.0.0.1/a.mp4','file:///tmp/a','http://user:password@example.com/video']:
            with self.assertRaises(ValueError): app.public_url(url)
        with self.assertRaises(ValueError): self.ws.submit({'url':'https://example.com/video'})

    def test_browser_import_is_job_scoped_and_preserves_notes(self):
        with patch.object(app, 'public_url', side_effect=lambda value: value):
            item = self.ws.submit({'url': 'https://example.com/video.mp4', 'authorized': True}, browser=True)
        self.ws.patch({'id': item['id'], 'revision': 0, 'notes': '保留浏览器下载中的笔记', 'shots': []})
        # An arbitrary local path must be rejected before FFmpeg or a file read.
        with patch('download_worker.probe_media') as probe:
            result = self.ws.finish_browser({'id': item['id'], 'filename': str(Path(self.temp.name) / 'private.mp4')})
            probe.assert_not_called()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['notes'], '保留浏览器下载中的笔记')
        self.assertNotIn('filename', result)
        self.assertNotIn('private.mp4', result['error'])

    def test_browser_upload_requires_auth_and_ordered_bounded_job_chunks(self):
        item = self.ws.submit({'url': 'https://example.com/video.mp4', 'authorized': True}, browser=True)
        path = '/api/workbench/browser-upload?id=' + item['id'] + '&offset=0'
        request = Request(self.url + path, b'abc', {'Content-Type': 'application/octet-stream'})
        with self.assertRaises(HTTPError) as denied: urlopen(request, timeout=5)
        self.assertEqual(denied.exception.code, 403)
        request.add_header('Authorization', 'Bearer ' + self.ws.token)
        with urlopen(request, timeout=5) as response: self.assertEqual(json.load(response)['receivedBytes'], 3)
        with self.assertRaises(ValueError): self.ws.upload_browser(item['id'], 'workbench', 0, b'duplicate')
        with self.assertRaises(ValueError): self.ws.upload_browser(item['id'], 'workbench', 3, b'x' * (4 * 1024**2 + 1))
        with self.assertRaises(ValueError): self.ws.upload_browser(item['id'], 'download', 3, b'wrong-store')
        self.ws.upload_browser(item['id'], 'workbench', 3, b'def')
        with patch.object(self.ws, 'finish_browser', return_value={'status': 'downloading'}) as finish:
            self.ws.upload_browser(item['id'], 'workbench', 6, b'', final=True)
            source = Path(finish.call_args.args[0]['filename'])
            self.assertEqual(source.name, item['browserFilename'])
            self.assertTrue(source.is_relative_to(self.ws.root / 'incoming' / item['id']))
            self.assertEqual(source.read_bytes(), b'abcdef')

    def test_clip_ranges_and_download_destination_are_validated_before_creation(self):
        common = {'url': 'https://example.com/video.mp4', 'authorized': True, 'destination': 'download', 'duration': 10}
        with patch.object(app, 'public_url', side_effect=lambda value: value):
            for start, end in [(-1, 2), (2, 2), (3, 2), (0, float('inf')), (True, 2), (0, 11), (None, 2)]:
                with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                    self.ws.submit({**common, 'clipStart': start, 'clipEnd': end}, browser=True)
            with self.assertRaises(ValueError): self.ws.submit(common, browser=True)
        self.assertEqual(self.ws.items(), [])
        self.assertEqual(self.ws.export_items(), [])

    def test_worker_state_transition_keeps_edits_and_hides_signed_url(self):
        gate = threading.Event()
        def fake_worker(record_id, url, source): gate.wait(3)
        with patch.object(app,'public_url',side_effect=lambda value:value), patch.object(self.ws,'download',side_effect=fake_worker):
            item = self.ws.submit({'authorized':True,'url':'https://cdn.example/video.mp4?token=secret','sourceUrl':'https://www.youtube.com/watch?v=id&token=secret'})
            self.assertNotIn('secret',json.dumps(self.ws.items()))
            self.ws.patch({'id':item['id'],'revision':0,'notes':'保留笔记','shots':[]})
            gate.set()
        self.assertEqual(self.ws.get(item['id'])['notes'],'保留笔记')

class QuietServer(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass

@unittest.skipUnless(ffmpeg_path() and importlib.util.find_spec('yt_dlp'), 'Install yt-dlp and FFmpeg for real fixture tests')
class MediaFixtureTests(unittest.TestCase):
    def test_mp4_hls_dash_real_worker(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            binary = ffmpeg_path()
            def ffmpeg(*args):
                subprocess.run([binary,'-hide_banner','-loglevel','error','-y',*args],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=45,cwd=root)
            ffmpeg('-f','lavfi','-i','color=c=green:s=320x180:r=25','-f','lavfi','-i','sine=frequency=440:sample_rate=44100','-t','2','-c:v','libx264','-pix_fmt','yuv420p','-g','25','-c:a','aac',str(root/'source.mp4'))
            ffmpeg('-i',str(root/'source.mp4'),'-c','copy','-hls_time','1','-hls_playlist_type','vod',str(root/'stream.m3u8'))
            ffmpeg('-i',str(root/'source.mp4'),'-c','copy','-f','dash',str(root/'stream.mpd'))
            from functools import partial
            server = ThreadingHTTPServer(('127.0.0.1',0),partial(QuietServer,directory=str(root)))
            thread = threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                for number, name in enumerate(['source.mp4','stream.m3u8','stream.mpd']):
                    with self.subTest(format=name):
                        folder = root/f'output-{number}';folder.mkdir()
                        url = f'http://127.0.0.1:{server.server_port}/{name}'
                        env = os.environ.copy();env.pop('SKILLTO_WORKBENCH_COOKIE_FILE',None)
                        worker = subprocess.run([sys.executable,str(Path(__file__).with_name('download_worker.py'))],
                            input=json.dumps({'url':url,'source':url,'folder':str(folder)}),capture_output=True,text=True,encoding='utf-8',timeout=60,env=env)
                        result = json.loads(worker.stdout)
                        self.assertTrue(result['ok'],result.get('error'))
                        self.assertEqual((result['width'], result['height']), (320, 180))
                        self.assertAlmostEqual(result['duration'], 2, delta=0.2)
                        media = folder/result['file']; self.assertGreater(media.stat().st_size,1000)
                        ffmpeg('-i',str(media),'-f','null','-')
            finally: server.shutdown();server.server_close();thread.join()

if __name__ == '__main__': unittest.main(verbosity=2)
