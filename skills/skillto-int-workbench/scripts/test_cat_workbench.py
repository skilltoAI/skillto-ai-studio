"""Real Cat Catch overlay UI + Chrome download + frame-accurate range export."""
import importlib.util
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import workbench as app
from build_cat_extension import build
from dependencies import ffmpeg_path
from download_worker import probe_media

UPSTREAM = Path(os.environ.get('CAT_CATCH_SOURCE', Path(__file__).resolve().parents[3] / 'work/reference-repos/cat-catch'))


@unittest.skipUnless(UPSTREAM.is_dir() and ffmpeg_path() and importlib.util.find_spec('playwright'), 'Requires Cat Catch source, FFmpeg and Playwright Chromium')
class CatWorkbenchTests(unittest.TestCase):
    def test_two_destinations_visual_range_and_license_branding(self):
        from playwright.sync_api import sync_playwright
        with tempfile.TemporaryDirectory(prefix='studio-cat-test-') as temp:
            root = Path(temp)
            sample = root / 'sample.mp4'
            binary = ffmpeg_path()
            subprocess.run([binary, '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'lavfi', '-i', 'color=c=red:s=320x180:r=25:d=2',
                '-f', 'lavfi', '-i', 'color=c=blue:s=320x180:r=25:d=3',
                '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100:duration=5',
                '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0[v]', '-map', '[v]', '-map', '2:a',
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-t', '5', str(sample)],
                check=True, capture_output=True, timeout=40)
            workspace = app.Workspace(root / 'data')

            class Handler(app.Handler):
                def do_GET(self):
                    if self.path == '/sample.mp4':
                        data = sample.read_bytes(); start, end = 0, len(data) - 1
                        match = re.fullmatch(r'bytes=(\d+)-(\d*)', self.headers.get('Range', ''))
                        if match:
                            start = int(match[1]); end = min(int(match[2]), end) if match[2] else end
                        self.send_response(206 if match else 200)
                        self.send_header('Content-Type', 'video/mp4'); self.send_header('Accept-Ranges', 'bytes')
                        self.send_header('Content-Length', str(end - start + 1))
                        if match: self.send_header('Content-Range', f'bytes {start}-{end}/{len(data)}')
                        self.end_headers(); self.wfile.write(data[start:end+1]); return
                    if self.path == '/fixture': return self.wb_send(b'<title>Video fixture</title><video controls width="320" height="180" src="/sample.mp4"></video>', 'text/html')
                    return super().do_GET()

            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            origin = f'http://127.0.0.1:{server.server_port}'
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            artifacts = Path(__file__).resolve().parents[3] / 'work'
            artifacts.mkdir(exist_ok=True)
            try:
                extension = build(UPSTREAM, root / 'extension')
                connection = extension / 'js/studio-connection.js'
                connection.write_text(connection.read_text(encoding='utf-8').replace('http://127.0.0.1:8880', origin), encoding='utf-8')
                downloads = root / 'downloads'; downloads.mkdir()
                profile = root / 'profile/Default'; profile.mkdir(parents=True)
                (profile / 'Preferences').write_text(json.dumps({'download': {'default_directory': str(downloads), 'prompt_for_download': False}}), encoding='utf-8')
                with patch.object(app, 'workspace', return_value=workspace), patch.object(app, 'public_url', side_effect=lambda value: value), sync_playwright() as pw:
                    context = pw.chromium.launch_persistent_context(str(root / 'profile'), channel='chromium', headless=True,
                        viewport={'width': 1280, 'height': 900}, args=[f'--disable-extensions-except={extension}', f'--load-extension={extension}'])
                    try:
                        worker = context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker')
                        extension_id = worker.url.split('/')[2]
                        page = context.new_page()
                        context.new_cdp_session(page).send('Browser.setDownloadBehavior', {'behavior': 'default'})
                        page.goto(f'chrome-extension://{extension_id}/install.html')
                        self.assertEqual(page.title(), '欢迎 · SKillto.ai|工作台')
                        self.assertFalse(page.locator('#agreeBtn').is_enabled())
                        page.locator('#agreement').check()
                        self.assertTrue(page.locator('#agreeBtn').is_enabled())
                        page.screenshot(path=str(artifacts / 'studio-cat-welcome.png'))
                        page.locator('#agreeBtn').click()
                        self.assertTrue(worker.evaluate('()=>chrome.storage.local.get("studioAccepted").then(v=>v.studioAccepted)'))
                        page.goto(f'chrome-extension://{extension_id}/credits.html')
                        self.assertIn('GPL v3', page.locator('body').inner_text())
                        fixture = context.new_page(); fixture.goto(origin + '/fixture')
                        fixture.locator('video').evaluate('(v)=>new Promise(r=>{if(v.readyState)r();else v.onloadedmetadata=r;})')
                        fixture_tab = worker.evaluate('(url)=>chrome.tabs.query({}).then(tabs=>tabs.find(t=>t.url===url).id)', origin + '/fixture')
                        popup = context.new_page(); popup.goto(f'chrome-extension://{extension_id}/popup.html?tabId={fixture_tab}')
                        popup.locator('.media-item').first.wait_for(timeout=15000)
                        self.assertEqual(popup.locator('.two-actions button').all_text_contents(), ['下载', '同步到工作台'])
                        self.assertEqual(popup.get_by_text('Aria2', exact=True).count(), 0)
                        with context.expect_page() as opened:
                            popup.locator('#download').click()
                        editor = opened.value; editor.wait_for_load_state()
                        errors = []; editor.on('pageerror', lambda error: errors.append(str(error)))
                        editor.locator('#properties').filter(has_text='320 × 180').wait_for(timeout=15000)
                        editor.locator('#download').click(force=True) if editor.locator('#download').is_enabled() else None
                        self.assertEqual(workspace.items(), [])
                        editor.locator('#authorized').check()
                        editor.locator('#download').click()
                        editor.get_by_role('status').filter(has_text='已交给 Chrome 下载').wait_for()
                        self.assertEqual(workspace.items(), [])
                        self.assertEqual(workspace.export_items(), [])
                        editor.locator('#player').evaluate('''v => {
                            const shown = (_, frame) => { v.dataset.presentedTime = frame.mediaTime; v.requestVideoFrameCallback(shown); };
                            v.requestVideoFrameCallback(shown);
                        }''')
                        # Both slider boundaries must pause playback and display their own frame.
                        editor.locator('#player').evaluate('v=>v.play()')
                        editor.locator('#startHandle').evaluate("e=>{e.value='0.8';e.dispatchEvent(new Event('input',{bubbles:true}));}")
                        editor.wait_for_function("()=>player.paused && !player.seeking && Math.abs(Number(player.dataset.presentedTime)-0.8)<0.05")
                        editor.locator('#endHandle').evaluate("e=>{e.value='3.8';e.dispatchEvent(new Event('input',{bubbles:true}));}")
                        editor.wait_for_function("()=>player.paused && !player.seeking && Math.abs(Number(player.dataset.presentedTime)-3.8)<0.05")
                        editor.locator('#startTime').fill('2.2'); editor.locator('#startTime').press('Tab')
                        editor.locator('#endTime').fill('3.2')
                        editor.wait_for_function("()=>player.paused && !player.seeking && Math.abs(Number(player.dataset.presentedTime)-3.2)<0.05")
                        editor.locator('#endTime').press('Tab')
                        self.assertTrue(editor.locator('#clipEnabled').is_checked())
                        editor.locator('#playSelection').click()
                        editor.wait_for_timeout(1300)
                        self.assertTrue(editor.locator('#player').evaluate('v=>v.paused && v.currentTime >= 2.2 && v.currentTime < 3.35'), editor.evaluate('()=>({paused:player.paused,time:player.currentTime,range:values(),selectionPlaying,hidden:document.hidden,status:document.getElementById("status").textContent})'))
                        editor.locator('#download').click()
                        editor.get_by_role('status').filter(has_text='所选片段已交给浏览器保存').wait_for(timeout=45000)
                        self.assertEqual(workspace.items(), [], 'Download-only export must not create a breakdown record')
                        exported = workspace.export_items()[0]
                        self.assertEqual(exported['status'], 'ready')
                        self.assertAlmostEqual(exported['duration'], 1, delta=0.12)
                        deadline = time.monotonic() + 15
                        saved = []
                        while time.monotonic() < deadline:
                            saved = worker.evaluate('()=>chrome.downloads.search({}).then(items=>items.filter(i=>i.state==="complete" && i.filename.includes("_片段")).map(i=>i.filename))')
                            if saved: break
                            editor.wait_for_timeout(100)
                        self.assertTrue(saved, 'Clipped browser download did not complete')
                        self.assertAlmostEqual(probe_media(Path(saved[0]))['duration'], 1, delta=0.12)
                        frame = subprocess.run([binary, '-hide_banner', '-loglevel', 'error', '-i', saved[0], '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True, timeout=20).stdout
                        offset = (90 * 320 + 160) * 3
                        self.assertGreater(frame[offset+2], frame[offset]+100, 'Selected range must begin in blue section, not red opening')
                        editor.locator('#workbench').click()
                        editor.get_by_role('status').filter(has_text='处理完成，已同步到工作台 · 拉片').wait_for(timeout=45000)
                        workspace_pages = [p for p in context.pages if p.url.startswith(origin + '/breakdowns?id=')]
                        self.assertEqual(len(workspace_pages), 1, 'Sync should open the workspace when absent')
                        workspace_tab = workspace_pages[0]
                        record = workspace.items()[0]
                        self.assertEqual(record['status'], 'ready')
                        self.assertAlmostEqual(record['duration'], 1, delta=0.12)
                        self.assertEqual((record['width'], record['height']), (320, 180))
                        self.assertEqual(record['clipStart'], 2.2)
                        processed = workspace.root / 'media' / record['id'] / record['file']
                        synced_frame = subprocess.run([binary, '-hide_banner', '-loglevel', 'error', '-i', str(processed), '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True, timeout=20).stdout
                        self.assertGreater(synced_frame[offset+2], synced_frame[offset]+100, 'Workbench must receive the processed selection, not the original opening')
                        self.assertEqual(len(workspace.export_items()), 1)
                        self.assertTrue(editor.locator('#openRecord').is_visible())
                        editor.screenshot(path=str(artifacts / 'studio-cat-editor.png'))
                        detail = workspace_tab
                        detail.locator('video').evaluate('async v=>{v.muted=true;await v.play();}')
                        self.assertFalse(detail.locator('video').evaluate('v=>!!v.error'))
                        # Re-pair through the already-open table workspace, without a new tab or configuration.
                        worker.evaluate('()=>chrome.storage.local.remove("studioToken")')
                        editor.locator('#workbench').click()
                        editor.get_by_role('status').filter(has_text='处理完成，已同步到工作台 · 拉片').wait_for(timeout=45000)
                        self.assertEqual(len(workspace.items()), 2)
                        self.assertEqual(len([p for p in context.pages if p.url.startswith(origin + '/breakdowns?id=')]), 1, 'Second sync must reuse the existing workspace tab')
                        self.assertNotIn(record['id'], detail.url)
                        self.assertEqual(worker.evaluate('()=>chrome.downloads.search({}).then(items=>items.filter(i=>i.filename.includes("SkilltoWorkbench")).length)'), 0, 'Sync must not depend on the browser download directory')
                        self.assertEqual(errors, [])
                    finally: context.close()
            finally:
                server.shutdown(); server.server_close(); thread.join(); workspace.close()


if __name__ == '__main__': unittest.main(verbosity=2)
