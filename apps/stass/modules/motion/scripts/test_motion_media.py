"""Demo threshold, dimensions, verified publication and temporary-input lifecycle."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import motion_media as m

URL='https://motiontemplates.github.io/385712/assets/demo.mp4'

def info(codec='h264',w=1920,h=1080):
    return {'streams':[{'codec_type':'video','codec_name':codec,'width':w,'height':h},{'codec_type':'audio','codec_name':'aac'}], 'format':{'duration':'3'}}

class MediaTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'SKILLTO_TABLE_ROOT':self.temp.name});self.env.start()
    def tearDown(self):self.env.stop();self.temp.cleanup()
    def large(self):
        raw,_=m.paths(URL);raw.parent.mkdir(parents=True,exist_ok=True)
        with raw.open('wb') as f:f.truncate(m.THRESHOLD+1)
        return raw
    def test_exact_threshold_unchanged(self):
        raw=self.large()
        with raw.open('wb') as f:f.truncate(m.THRESHOLD)
        with patch.object(m,'probe') as probe:
            self.assertEqual(m.ensure_preview(URL,{'PATH':''}),raw);probe.assert_not_called()
    def test_background_small_does_not_download(self):
        with patch.object(m,'source_size',return_value=m.THRESHOLD),patch.object(m,'download') as download:
            self.assertIsNone(m.ensure_preview(URL,{'PATH':''},inspect_only=True));download.assert_not_called()
    def test_transcode_validate_delete_and_reuse(self):
        raw=self.large();_,derived=m.paths(URL);commands=[]
        def encode(args):commands.append(args);Path(args[-1]).write_bytes(b'encoded')
        with patch.object(m.shutil,'which',return_value='ffmpeg'),patch.object(m,'probe',side_effect=[info(),info('hevc',1280,720)]):
            self.assertEqual(m.ensure_preview(URL,{'PATH':''},execute=encode),derived)
        self.assertFalse(raw.exists());self.assertTrue(derived.with_suffix('.json').is_file())
        self.assertIn('libx265',commands[0]);self.assertIn('hvc1',commands[0])
        with patch.object(m,'download') as download:
            self.assertEqual(m.ensure_preview(URL,{'PATH':''}),derived);download.assert_not_called()
    def test_failed_and_cancelled_encoding_cleans_inputs(self):
        for error in (ValueError('bad encoder'),InterruptedError('cancelled')):
            raw=self.large();_,derived=m.paths(URL)
            def fail(args):Path(args[-1]).write_bytes(b'partial');raise error
            with patch.object(m.shutil,'which',return_value='ffmpeg'),patch.object(m,'probe',return_value=info()),self.assertRaises(type(error)):
                m.ensure_preview(URL,{'PATH':''},execute=fail)
            self.assertFalse(raw.exists());self.assertFalse(derived.exists());self.assertFalse(derived.with_suffix('.part.mp4').exists())
    def test_validation_failure_does_not_publish(self):
        raw=self.large();_,derived=m.paths(URL)
        with patch.object(m.shutil,'which',return_value='ffmpeg'),patch.object(m,'probe',side_effect=[info(),info('h264',1280,720)]),self.assertRaises(ValueError):
            m.ensure_preview(URL,{'PATH':''},execute=lambda args:Path(args[-1]).write_bytes(b'bad'))
        self.assertFalse(raw.exists());self.assertFalse(derived.exists())
    def test_portrait_and_no_upscale_dimensions(self):
        self.assertIn('720',m.scale_filter(1080,1920));self.assertIn('1280',m.scale_filter(1080,1920));self.assertIn('min(iw',m.scale_filter(360,640))
    def test_new_large_download_is_temporary(self):
        def fetch(url,path,limit,cancel):
            self.assertIn('.source.',path.name);path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('wb') as f:f.truncate(m.THRESHOLD+1)
        raw,derived=m.paths(URL)
        with patch.object(m,'download',side_effect=fetch),patch.object(m.shutil,'which',return_value=None),self.assertRaises(ValueError):
            m.ensure_preview(URL,{'PATH':''})
        self.assertFalse(raw.exists());self.assertFalse(raw.with_suffix('.source.mp4').exists())

if __name__=='__main__':unittest.main(verbosity=2)
