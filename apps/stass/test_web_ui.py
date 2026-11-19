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
                    item=page.evaluate('''async ({id}) => {
                      async function post(path, body) {
                        const response=await fetch('/STASS/api/v1/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
                        const result=await response.json();
                        if(!response.ok) throw Error(JSON.stringify(result));
                        return result;
                      }
                      const project=await post('workspace',{action:'create',level:'project',knowledgeBaseId:id,name:'Tables'});
                      const table=await post('workspace',{action:'create',level:'table',knowledgeBaseId:id,projectId:project.id,name:'Embedded Board'});
                      await post('define',{tableId:table.id,fields:[{name:'name',label:'社区名称',type:'text'},{name:'manualProcessing',label:'人工处理备注',type:'text'}]});
                      await post('row',{action:'create',tableId:table.id,fields:{name:'Fixture community'}});
                      const kb=await post('rewrites',{action:'create_kb',name:'Fixture'});
                      const drafts=await post('rewrites',{action:'create_project',knowledgeBaseId:kb.id,name:'Drafts'});
                      const sections=Object.fromEntries('claims scenario counterintuitive value similar traffic audience cases'.split(' ').map(key=>[key,{text:'',score:null,scoreNote:''}]));
                      const similar={douyin:[],xiaohongshu:[],youtube:[],x:[]};
                      const draft=await post('rewrites',{action:'create',knowledgeBaseId:kb.id,projectId:drafts.id,manuscript:{title:'Embedded fixture',transcript:'[00:00] Source',sections,similar}});
                      await post('rewrites',{action:'link_motion_storyboard',id:draft.id,tableId:table.id,expectedRevision:0});
                      return {draftId:draft.id,tableId:table.id};
                    }''',result['body'])
                    page.goto(state['url']+'?table='+item['tableId'])
                    row=page.locator('tbody tr[data-id]').first
                    page.get_by_role('button',name='字段排序',exact=True).click()
                    order = page.get_by_role('dialog',name='字段排序')
                    order.get_by_role('listbox',name='字段顺序').select_option('manualProcessing')
                    order.get_by_role('button',name='移到首列').click()
                    order.get_by_role('button',name='保存顺序').click()
                    order.wait_for(state='detached')
                    self.assertIn('人工处理备注',page.locator('#tableHead th').first.inner_text())
                    filters = page.locator('.schema-filter-panel')
                    filters.locator('summary').click()
                    filters.get_by_role('searchbox', name='社区名称').fill('不存在')
                    self.assertEqual(row.count(), 0)
                    filters.locator('summary').click()
                    page.get_by_role('button', name='清除筛选 社区名称：不存在').click()
                    row.wait_for()
                    row.get_by_role('button',name='编辑人工处理备注').click()
                    inline_note=row.get_by_role('textbox',name='人工处理备注')
                    inline_note.fill('单元格内填写\n已核对')
                    row.get_by_role('button',name='保存备注').click()
                    row.get_by_text('已核对',exact=False).wait_for()
                    page.reload()
                    row.get_by_text('已核对',exact=False).wait_for()
                    self.assertIn('人工处理备注',page.locator('#tableHead th').first.inner_text())
                    origin = {'Origin':state['url'].removesuffix('/STASS/')}
                    stale_order = page.request.post(state['url']+'api/v1/define',headers=origin,
                        data={'tableId':item['tableId'],'fieldOrder':['name','manualProcessing'],
                              'expectedFieldOrder':['name','manualProcessing']})
                    self.assertEqual(stale_order.status,400)
                    stale_note = page.request.post(state['url']+'api/v1/row',headers=origin,
                        data={'tableId':item['tableId'],'rowId':row.get_attribute('data-id'),'action':'update',
                              'fields':{'manualProcessing':'旧页面覆盖'},'expectedFields':{'manualProcessing':None}})
                    self.assertEqual(stale_note.status,400)
                    row.locator('[data-action=edit]').click()
                    note=page.get_by_role('textbox',name='人工处理备注')
                    self.assertEqual(note.input_value(),'单元格内填写\n已核对')
                    note.fill('已联系运营方\n等待回复')
                    page.locator('#rowForm').get_by_role('button',name='保存',exact=True).click()
                    row.get_by_text('等待回复',exact=False).wait_for()
                    page.reload()
                    row.get_by_text('等待回复',exact=False).wait_for()
                    row.locator('[data-action=edit]').click()
                    self.assertEqual(note.input_value(),'已联系运营方\n等待回复')
                    self.assertEqual(page.get_by_role('textbox',name='社区名称').input_value(),'Fixture community')
                    page.locator('#rowDialog .close-modal').click()
                    page.goto(state['url']+'?section=rewrites&manuscript='+item['draftId']+'&rewriteTab=motionStoryboard')
                    frame=page.frame_locator('iframe.rewrite-motion-table')
                    frame.locator('#tableTitle:text-is("Embedded Board")').wait_for()
                    self.assertEqual(page.locator('iframe.rewrite-motion-table').get_attribute('data-table-loaded'),'1')
                    page.get_by_role('tab',name='文案版本').click()
                    page.locator('iframe.rewrite-motion-table').wait_for(state='detached')
                    editor = page.locator('.rewrite-version-text')
                    editor.wait_for()
                    self.assertLess(editor.bounding_box()['y'], 330)
                    self.assertEqual(page.locator('.rewrite-step-marker').all_text_contents(), ['1','2','3','4','5'])
                    page.get_by_role('button', name='新增版本').click()
                    page.locator('[data-version-choice="v1"][aria-pressed="true"]').wait_for()
                    page.locator('[data-version-choice="v0"]').click()
                    page.locator('[data-version-choice="v0"][aria-pressed="true"]').wait_for()
                    self.assertTrue(editor.evaluate('(input) => input.readOnly'))
                    page.get_by_role('button', name='双版本编辑').click()
                    page.get_by_role('textbox', name='左侧版本正文').wait_for()
                    page.get_by_role('button', name='单版本编辑').click()
                    page.set_viewport_size({'width':390, 'height':844})
                    self.assertFalse(page.locator('#rewrite-sidebar').is_visible())
                    page.get_by_role('button', name='稿件目录', exact=True).click()
                    self.assertTrue(page.locator('#rewrite-sidebar').is_visible())
                    page.get_by_role('button', name='稿件目录', exact=True).click()
                    self.assertEqual(page.evaluate('document.documentElement.scrollWidth'),390)
                    page.set_viewport_size({'width':1280, 'height':720})
                    self.assertEqual(errors,[])
                    self.assertEqual(failed_assets,[])
                    logo=page.locator('.workspace-nav-brand img')
                    self.assertTrue(logo.evaluate('(img) => img.complete && img.naturalWidth > 0'))
                    page.get_by_role('link',name='拉片',exact=True).click()
                    page.wait_for_load_state('networkidle')
                    self.assertTrue(page.url.startswith(state['url']))
                    page.set_viewport_size({'width':320, 'height':720})
                    directory = page.get_by_role('button', name='打开目录', exact=True)
                    directory.click()
                    self.assertTrue(page.locator('#search').is_visible())
                    page.keyboard.press('Escape')
                    self.assertFalse(page.locator('#search').is_visible())
                    page.goto(state['url']+'browser-users')
                    self.assertEqual(page.locator('.workspace-nav-links > *').count(), 9)
                    self.assertEqual(page.locator('[aria-current=page]').inner_text(), '浏览器用户')
                    self.assertEqual(page.evaluate('document.documentElement.scrollWidth'), 320)
                    page.get_by_text('暂无浏览器用户，请先创建。',exact=True).wait_for()
                    self.assertEqual(failed_assets,[])
                    self.assertEqual(errors,[])
                    browser.close()
            finally: stop(root)


if __name__=='__main__':unittest.main()
