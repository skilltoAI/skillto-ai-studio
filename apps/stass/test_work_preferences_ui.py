"""Real browser coverage using an isolated service, skill destination and preferences."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from runtime_control import register_development, start, stop
import work_profiles


class PreferencesBrowserTests(unittest.TestCase):
    def test_manage_and_recheck_in_shared_web(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {
            'STASS_PREFERENCES_DIR':str(Path(temp)/'prefs'), 'CLAUDE_CONFIG_DIR':str(Path(temp)/'claude'),
        }):
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            root = Path(temp)/'instance'
            state = register_development(root, Path(__file__).parent, sys.executable, port)
            start(root)
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch()
                    page = browser.new_page()
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    url = state['url']
                    page.goto(url)
                    page.get_by_text('按我的工作整理界面', exact=True).wait_for()
                    page.get_by_text('按我的工作整理界面', exact=True).click()
                    page.locator('#host').select_option('claude')
                    page.get_by_label('教学内容制作', exact=True).check()
                    page.evaluate("Object.defineProperty(navigator,'clipboard',{value:{writeText:async()=>{throw Error('denied')}}})")
                    page.locator('#save').click()
                    page.get_by_text('请复制已选中的提示词，在客户端中运行。').wait_for()
                    self.assertIn('--groups teach', page.locator('textarea').input_value())
                    self.assertEqual(work_profiles.profile()['groups'], ['teach'])
                    subprocess.run([sys.executable, str(work_profiles.ROOT/'scripts/install.py'), '--agent','claude',
                                    '--groups','teach'], check=True, capture_output=True)
                    page.locator('#detect').click()
                    page.get_by_role('button', name='保存界面设置', exact=True).wait_for()
                    page.get_by_label('AI视频剪辑', exact=True).check()
                    page.evaluate("navigator.clipboard.writeText=async t=>{window.featureClipboard=t}")
                    page.locator('#save').click()
                    page.get_by_text('安装提示词已复制。',exact=False).wait_for()
                    self.assertIn('talking-head-edit', page.evaluate('window.featureClipboard'))
                    page.goto(url)
                    page.get_by_role('link',name='打开视频拉片',exact=True).wait_for()
                    self.assertTrue(page.get_by_role('link',name='打开分镜审阅').is_visible())
                    page.goto(url+'features.html')
                    page.get_by_label('AI视频剪辑',exact=True).uncheck()
                    page.get_by_role('button',name='保存界面设置',exact=True).click()
                    page.get_by_text('界面设置已保存。').wait_for()
                    self.assertNotIn('talking-head-edit',work_profiles.profile()['items'])
                    page.goto(url)
                    page.get_by_role('link',name='打开分镜审阅').wait_for()
                    self.assertEqual(page.get_by_role('link',name='打开视频拉片',exact=True).count(),0)
                    page.goto(url+'?section=motions')
                    self.assertEqual(page.locator('.workspace-section').get_attribute('data-view'),'motions')
                    page.goto(url+'features.html')
                    page.locator('#host').select_option('workbody')
                    page.locator('#advanced summary').first.click()
                    page.get_by_text('宿主待验证',exact=True).first.wait_for()
                    self.assertEqual(errors, [])
                    browser.close()
            finally:
                stop(root)
