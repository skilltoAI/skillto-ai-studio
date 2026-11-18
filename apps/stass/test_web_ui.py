import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
import urllib.request

from runtime_control import register_development,start,stop


class WebTests(unittest.TestCase):
    def test_pairing_real_browser_navigation_and_shared_table(self):
        from playwright.sync_api import sync_playwright
        with tempfile.TemporaryDirectory(prefix='STASS 网页 ') as temporary:
            root=Path(temporary)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            state=register_development(root,Path(__file__).parent,sys.executable,port)
            start(root)
            try:
                token=(root/'config/admin.token').read_text()
                request=urllib.request.Request(state['url']+'api/v1/pair-code',headers={'Authorization':'Bearer '+token})
                with urllib.request.urlopen(request) as response: code=json.load(response)['code']
                with sync_playwright() as pw:
                    browser=pw.chromium.launch(headless=True)
                    page=browser.new_page()
                    errors=[]
                    failed_assets=[]
                    page.on('pageerror',lambda error: errors.append(str(error)))
                    page.on('response',lambda response: failed_assets.append(response.url) if response.status>=400 and any(response.url.split('?')[0].endswith(ext) for ext in ('.js','.css','.png')) else None)
                    page.goto(state['url'])
                    self.assertEqual(page.url,state['url'])
                    page.goto(state['url']+'pair')
                    self.assertEqual(page.url,state['url'])
                    page.wait_for_selector('.workspace-nav')
                    for name in ('表格','报表','洗稿','Motion 模版','文档','排稿','工具'):
                        page.get_by_role('button',name=name,exact=True).click()
                    page.get_by_role('button',name='表格',exact=True).click()
                    result=page.evaluate('''async () => {
                      const response=await fetch('/STASS/api/v1/workspace',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'create',level:'knowledge_base',name:'Browser shared'})});
                      return {status:response.status,body:await response.json()};
                    }''')
                    self.assertEqual(result['status'],200,result)
                    request=urllib.request.Request(state['url']+'api/v1/tools/table_workspace',data=b'{}',headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
                    with urllib.request.urlopen(request) as response:
                        self.assertEqual(json.load(response)['result']['knowledgeBases'][0]['id'],result['body']['id'])
                    self.assertEqual(errors,[])
                    self.assertEqual(failed_assets,[])
                    logo=page.locator('.workspace-nav-brand img')
                    self.assertTrue(logo.evaluate('(img) => img.complete && img.naturalWidth > 0'))
                    page.get_by_role('link',name='拉片',exact=True).click()
                    page.wait_for_load_state('networkidle')
                    self.assertTrue(page.url.startswith(state['url']))
                    page.goto(state['url']+'browser-users')
                    page.wait_for_load_state('networkidle')
                    self.assertEqual(errors,[])
                    browser.close()
            finally: stop(root)


if __name__=='__main__':unittest.main()
