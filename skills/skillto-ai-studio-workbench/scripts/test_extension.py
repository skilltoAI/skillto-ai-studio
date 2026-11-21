"""Real unpacked-extension test, isolated profile/data and generated local media."""
import importlib.util
import json
from pathlib import Path
import subprocess
import shutil
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import workbench as app
from dependencies import ffmpeg_path


@unittest.skipUnless(importlib.util.find_spec('playwright') and ffmpeg_path(), 'Requires Playwright Chromium and FFmpeg')
class ExtensionTests(unittest.TestCase):
    def test_automatic_connection_download_metadata_and_playback(self):
        from playwright.sync_api import sync_playwright
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sample = root / 'sample.mp4'
            subprocess.run([ffmpeg_path(), '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'lavfi', '-i', 'color=c=green:s=320x180:r=25',
                '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100',
                '-t', '2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(sample)],
                check=True, capture_output=True, timeout=30)
            workspace = app.Workspace(root / 'data')

            class Handler(app.Handler):
                def do_GET(self):
                    if self.path == '/sample.mp4':
                        return self.wb_send(sample.read_bytes(), 'video/mp4')
                    if self.path == '/test-video':
                        return self.wb_send(b'<title>Extension fixture</title><video controls width="320" src="/sample.mp4"></video>', 'text/html')
                    return super().do_GET()

            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            origin = f'http://127.0.0.1:{server.server_port}'
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                # Only this isolated fixture accepts local media. Production validation is unchanged.
                with patch.object(app, 'workspace', return_value=workspace), patch.object(app, 'public_url', side_effect=lambda value: value), sync_playwright() as pw:
                    source_extension = Path(__file__).resolve().parents[1] / 'assets' / 'extension'
                    extension = root / 'extension'
                    shutil.copytree(source_extension, extension)
                    # Test-only permission grant avoids automating Chrome's human permission UI.
                    manifest = json.loads((extension / 'manifest.json').read_text(encoding='utf-8'))
                    manifest['permissions'].append('downloads')
                    manifest['optional_permissions'].remove('downloads')
                    manifest['host_permissions'].append('https://www.douyin.com/*')
                    (extension / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
                    # Redirect the launcher's default origin to the isolated service;
                    # no production service/token is used by this fixture.
                    connection = extension / 'connection.js'
                    connection.write_text(connection.read_text(encoding='utf-8').replace('http://127.0.0.1:8880', origin), encoding='utf-8')
                    downloads = root / 'downloads'; downloads.mkdir()
                    fixture_profile = root / 'profile' / 'Default'; fixture_profile.mkdir(parents=True)
                    # Only a new disposable test profile is configured, never user Chrome preferences.
                    (fixture_profile / 'Preferences').write_text(json.dumps({'download': {'default_directory': str(downloads), 'prompt_for_download': False}}), encoding='utf-8')
                    context = pw.chromium.launch_persistent_context(str(root / 'profile'), channel='chromium', headless=True,
                        args=[f'--disable-extensions-except={extension}', f'--load-extension={extension}'])
                    try:
                        worker = context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker')
                        extension_id = worker.url.split('/')[2]
                        cdp = context.new_cdp_session(context.pages[0])
                        cdp.send('Browser.setDownloadBehavior', {'behavior': 'default'})
                        # No token or endpoint is seeded. The local page supplies both automatically.
                        local = context.new_page()
                        local.goto(origin + '/breakdowns')
                        deadline = time.monotonic() + 15
                        while time.monotonic() < deadline:
                            paired = worker.evaluate('async () => {const c = await chrome.storage.local.get(["endpoint","token"]);return {origin:c.endpoint, paired:!!c.token};}')
                            if paired == {'origin': origin, 'paired': True}:
                                break
                            local.wait_for_timeout(100)
                        self.assertEqual(paired, {'origin': origin, 'paired': True})
                        # A stale token also heals through the same-origin bridge, with no user fields.
                        worker.evaluate('() => chrome.storage.local.remove("token")')
                        page = context.new_page()
                        errors = []
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.goto(f'chrome-extension://{extension_id}/popup.html')
                        page.get_by_text('已自动连接本地工作台', exact=True).wait_for(timeout=20000)
                        self.assertEqual(page.locator('input[type=password], #endpoint, #token').count(), 0)
                        local.goto(origin + '/test-video')
                        local.locator('video').evaluate('(v) => new Promise(resolve => {if(v.readyState)resolve();else v.onloadedmetadata=resolve;})')
                        tab_id = worker.evaluate('(url) => chrome.tabs.query({}).then(tabs => tabs.find(tab => tab.url === url).id)', origin + '/test-video')
                        # Opening popup.html as a test tab has no browser-action activeTab context.
                        page.evaluate('(value) => {tab = value;}', {'id': tab_id, 'url': origin + '/test-video', 'title': 'Extension fixture'})
                        page.locator('#scan').click()
                        page.locator('#resourceInfo').filter(has_text='320 × 180').wait_for()
                        page.locator('#preview').click()
                        deadline = time.monotonic() + 10
                        while page.locator('#previewPlayer').evaluate('v => v.readyState') < 2 and time.monotonic() < deadline:
                            page.wait_for_timeout(100)
                        self.assertGreaterEqual(page.locator('#previewPlayer').evaluate('v => v.readyState'), 2)
                        page.locator('#downloadResource').click()
                        page.get_by_role('status').filter(has_text='请先确认下载授权').wait_for()
                        self.assertEqual(workspace.items(), [])
                        page.locator('#authorized').check()
                        page.locator('#downloadResource').click()
                        page.get_by_role('status').filter(has_text='下载完成').wait_for(timeout=15000)
                        record = workspace.items()[0]
                        self.assertEqual(record['status'], 'ready')
                        self.assertEqual((record['width'], record['height']), (320, 180))
                        self.assertGreater(record['bytes'], 1000)
                        local.goto(origin + '/breakdowns?id=' + record['id'])
                        local.locator('#mediaProperties').filter(has_text='320 × 180').wait_for()
                        local.locator('video').evaluate('async v => {v.muted=true;await v.play();v.currentTime=1;}')
                        deadline = time.monotonic() + 10
                        while not local.locator('video').evaluate('v => v.readyState >= 2 && v.currentTime >= 1') and time.monotonic() < deadline:
                            local.wait_for_timeout(100)
                        self.assertTrue(local.locator('video').evaluate('v => v.readyState >= 2 && v.currentTime >= 1'))
                        # Reproduce the real failure shape: a blob player and current-item
                        # JSON on a modal URL. No external Douyin request/session is used.
                        douyin_url = 'https://www.douyin.com/user/fixture?modal_id=123'
                        data = {'aweme_id': '123', 'video': {'play_addr': {'url_list': [origin + '/sample.mp4']},
                            'width': 320, 'height': 180, 'duration': 2000}}
                        html = '<video width="320" height="180" src="blob:fixture"></video><script id="RENDER_DATA" type="application/json">'+json.dumps(data)+'</script>'
                        context.route('https://www.douyin.com/**', lambda route: route.fulfill(status=200, content_type='text/html', body=html))
                        local.goto(douyin_url)
                        page.evaluate('(value) => {tab = value;}', {'id': tab_id, 'url': douyin_url, 'title': 'Current blob fixture'})
                        page.locator('#download').click()
                        page.get_by_role('status').filter(has_text='下载完成').wait_for(timeout=15000)
                        self.assertEqual(len(workspace.items()), 2)
                        self.assertTrue(all(row.get('transfer') == 'browser' for row in workspace.items()))
                        self.assertTrue(all(row['status'] == 'ready' for row in workspace.items()))
                        self.assertEqual(len(list((downloads / 'SkilltoWorkbench').glob('*.mp4'))), 2)
                        # An unrelated cached item must never be silently downloaded or
                        # handed to yt-dlp as a page fallback.
                        local.goto(douyin_url.replace('123', '999'))
                        page.evaluate('(value) => {tab = value;}', {'id': tab_id, 'url': douyin_url.replace('123', '999'), 'title': 'Unmatched fixture'})
                        page.locator('#download').click()
                        page.get_by_role('status').filter(has_text='页面详情未返回视频数据').wait_for()
                        self.assertEqual(len(workspace.items()), 2)
                        self.assertEqual(errors, [])
                        screenshot = Path(__file__).resolve().parents[3] / 'work' / 'workbench-0.2-popup.png'
                        screenshot.parent.mkdir(exist_ok=True)
                        page.screenshot(path=str(screenshot))
                        local.screenshot(path=str(screenshot.with_name('workbench-0.2-playback.png')))
                    finally:
                        context.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
                workspace.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
