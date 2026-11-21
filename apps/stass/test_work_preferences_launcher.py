"""Exercise the embedded launcher assets and offline Python protocol in Chromium."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


class LauncherPreferencesTests(unittest.TestCase):
    def test_offline_window_persists_and_filters(self):
        program = Path(__file__).parent.resolve()
        assets = program / 'modules/table/scripts/windows/ui'
        with tempfile.TemporaryDirectory() as temp, sync_playwright() as pw:
            prefs = Path(temp)/'preferences'
            env = dict(os.environ, STASS_PREFERENCES_DIR=str(prefs), CLAUDE_CONFIG_DIR=str(Path(temp)/'claude'))

            def bridge(request):
                result = subprocess.run([sys.executable,'-B','-X','utf8',str(program/'work_profiles.py')],
                                        input=request, encoding='utf-8', env=env, capture_output=True, check=True)
                return result.stdout

            browser = pw.chromium.launch()
            page = browser.new_page()
            page.expose_function('inspectPreferences', bridge)
            page.add_init_script("""window.go={main:{Launcher:{
                WorkPreferences: request=>window.inspectPreferences(request),
                State: async()=>({phase:'stopped',running:false,url:''})}}};
                window.runtime={EventsOn:()=>{},ClipboardSetText:async text=>{window.copied=text;return true}};""")
            def serve_assets(route):
                path = urlsplit(route.request.url).path.strip('/') or 'index.html'
                route.fulfill(path=str(assets/path))
            page.route('http://launcher.test/**', serve_assets)
            page.goto('http://launcher.test/')
            page.get_by_text('服务已关闭',exact=True).wait_for()
            page.locator('#features').click()
            manager = page.frame_locator('#featureDlg iframe')
            manager.locator('#host').select_option('claude')
            manager.get_by_label('教学内容制作',exact=True).check()
            manager.locator('#save').click()
            manager.get_by_text('安装提示词已复制。',exact=False).wait_for()
            self.assertIn('--groups teach',page.evaluate('window.copied'))
            self.assertEqual(json.loads((prefs/'work.json').read_text(encoding='utf-8'))['groups'],['teach'])
            manager.locator('#back').click()
            page.locator('#featureDlg').wait_for(state='hidden')
            page.get_by_role('tab',name='Motion',exact=True).wait_for(state='hidden')
            self.assertFalse(page.locator('#open').is_enabled())
            browser.close()
