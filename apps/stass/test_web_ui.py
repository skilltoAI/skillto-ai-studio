import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
import urllib.request

from runtime_control import register_development,start,stop


class WebTests(unittest.TestCase):
    def test_browser_platform_shortcuts_use_the_selected_profile(self):
        from playwright.sync_api import sync_playwright, expect

        platforms = {
            '抖音': 'https://www.douyin.com/',
            '小红书': 'https://www.xiaohongshu.com/explore',
            '视频号创作者中心': 'https://channels.weixin.qq.com/platform/',
            'TikTok': 'https://www.tiktok.com/',
            'X': 'https://x.com/',
            'Instagram': 'https://www.instagram.com/',
            'B站': 'https://www.bilibili.com/',
        }
        profiles = [
            {'id': 'profile-a', 'name': '浏览器甲', 'running': False},
            {'id': 'profile-b', 'name': '浏览器乙', 'running': True},
        ]
        requests = []

        def browser_api(route):
            args = route.request.post_data_json
            if args['action'] == 'list':
                route.fulfill(json={'result': {'users': profiles}})
                return
            requests.append(args)
            route.fulfill(json={'result': {}})

        with tempfile.TemporaryDirectory(prefix='STASS shortcuts ') as temporary:
            root = Path(temporary)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            state = register_development(root, Path(__file__).parent, sys.executable, port)
            start(root)
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True)
                    page = browser.new_page(viewport={'width': 320, 'height': 720})
                    page.route(state['url'] + 'api/v1/browser', browser_api)
                    page.goto(state['url'] + 'browser-users')
                    for profile in profiles:
                        group = page.get_by_role('group', name=profile['name'] + '的平台入口')
                        expect(group.get_by_role('button')).to_have_count(len(platforms))
                        for label, url in platforms.items():
                            button = group.get_by_role('button', name='打开' + label, exact=True)
                            icon = button.locator('svg use')
                            symbol_id = icon.get_attribute('href')
                            expect(page.locator(symbol_id)).to_have_count(1)
                            button.press('Enter')
                            expect(page.get_by_role('status').filter(has_text='已在')).to_contain_text(label)
                            self.assertEqual(requests[-2:], [
                                {'action': 'launch', 'userId': profile['id']},
                                {'action': 'new_page', 'userId': profile['id'], 'url': url},
                            ])
                    self.assertEqual(page.evaluate('document.documentElement.scrollWidth'), 320)
                    browser.close()
            finally:
                stop(root)

    def test_pairing_real_browser_navigation_and_shared_table(self):
        from playwright.sync_api import sync_playwright, expect
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
                    for name in ('表格','报表','洗稿','AI资产','文档','排稿','工具'):
                        page.get_by_role('button',name=name,exact=True).click()
                        if name == '文档':
                            expect(page.get_by_text('暂无文档。可以添加自己的飞书或其他 HTTPS 文档链接。')).to_be_visible()
                            page.get_by_label('文档名称').fill('本机测试文档')
                            page.get_by_label('HTTPS 文档链接').fill('https://example.test/document')
                            page.get_by_role('button', name='添加文档').click()
                            expect(page.get_by_role('link', name='本机测试文档')).to_have_attribute('href', 'https://example.test/document')
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
                      await post('define',{tableId:table.id,fields:[{name:'name',label:'社区名称',type:'text'},{name:'manualProcessing',label:'人工处理备注',type:'text'},{name:'userFeedback',label:'用户修改意见',type:'text'}]});
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
                    page.get_by_role('button',name='字段排序',exact=True).click()
                    order.get_by_role('listbox',name='字段顺序').select_option('__rating__')
                    order.get_by_role('button',name='移到首列').click()
                    order.get_by_role('button',name='保存顺序').click()
                    order.wait_for(state='detached')
                    self.assertIn('评分',page.locator('#tableHead th').first.inner_text())
                    self.assertEqual(row.locator('td').first.locator('[data-action=review]').count(), 1)
                    page.reload()
                    page.locator('#tableHead th').first.get_by_role('button',name='评分排序').wait_for()
                    # Hiding the anchor field must not move rating back to the end.
                    page.locator('.schema-column-panel summary').click()
                    page.locator('[data-column="manualProcessing"]').uncheck()
                    self.assertIn('评分',page.locator('#tableHead th').first.inner_text())
                    page.locator('[data-column="manualProcessing"]').check()
                    page.locator('.schema-column-panel summary').click()
                    page.get_by_role('button',name='字段排序',exact=True).click()
                    order.get_by_role('listbox',name='字段顺序').select_option('__rating__')
                    order.get_by_role('button',name='↓ 下移').click()
                    order.get_by_role('button',name='保存顺序').click()
                    order.wait_for(state='detached')
                    self.assertIn('评分',page.locator('#tableHead th').nth(1).inner_text())
                    rating = row.get_by_role('slider', name='评分', exact=True)
                    self.assertEqual(rating.locator('.table-rate-star').count(), 5)
                    self.assertLessEqual(rating.bounding_box()['width'], 80)
                    rating.hover(position={'x':34,'y':12})
                    self.assertEqual(rating.get_attribute('aria-valuenow'), '0')
                    self.assertEqual(rating.locator('.table-rate-fill').nth(2).get_attribute('style'), 'width: 50%;')
                    rating.click(position={'x':34,'y':12})
                    expect(rating).to_have_attribute('aria-valuenow','2.5')
                    expect(rating).to_have_attribute('aria-busy','false')
                    page.reload()
                    expect(rating).to_have_attribute('aria-valuenow','2.5')
                    row.get_by_role('button', name='评分说明').click()
                    self.assertEqual(page.locator('#scoreInput').input_value(), '2.5')
                    page.locator('#scoreNote').fill('保留人工说明')
                    page.locator('#saveReview').click()
                    page.locator('#reviewDialog').wait_for(state='hidden')
                    expect(rating).to_have_attribute('aria-valuenow','2.5')
                    rating.press('ArrowRight')
                    expect(rating).to_have_attribute('aria-valuenow','3')
                    rating.click(position={'x':4,'y':12})
                    expect(rating).to_have_attribute('aria-valuenow','0.5')
                    # Failure restores the persisted score and keeps the control usable.
                    page.route('**/api/v1/review', lambda route: route.fulfill(status=500,content_type='application/json',body='{"error":"fixture failure"}'))
                    rating.click(position={'x':73,'y':12})
                    expect(page.locator('#notice')).to_contain_text('评分保存失败')
                    expect(rating).to_have_attribute('aria-busy','false')
                    expect(rating).to_have_attribute('aria-valuenow','0.5')
                    page.unroute('**/api/v1/review')
                    rating.click(position={'x':73,'y':12})
                    expect(rating).to_have_attribute('aria-valuenow','5')
                    # Clicking the current score clears it without clearing its rationale.
                    rating.click(position={'x':73,'y':12})
                    expect(rating).to_have_attribute('aria-valuenow','0')
                    stored = page.request.get(state['url']+'api/v1/table?id='+item['tableId']).json()['rows'][0]
                    self.assertEqual(stored['rating'], {'score':None,'note':'保留人工说明'})
                    touch = browser.new_context(has_touch=True, viewport={'width':390,'height':844})
                    touch_page = touch.new_page()
                    touch_page.goto(state['url']+'?table='+item['tableId'])
                    touch_rating = touch_page.get_by_role('slider',name='评分',exact=True)
                    touch_rating.scroll_into_view_if_needed()
                    box = touch_rating.bounding_box()
                    touch_page.touchscreen.tap(box['x']+34,box['y']+12)
                    expect(touch_rating).to_have_attribute('aria-valuenow','2.5')
                    touch.close()
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
                    fields=page.request.get(state['url']+'api/v1/table?id='+item['tableId']).json()['fields']
                    fields.append({'name':'renderedVideo','label':'完整成片','type':'video'})
                    self.assertTrue(page.request.post(state['url']+'api/v1/define',headers=origin,
                        data={'tableId':item['tableId'],'fields':fields}).ok)
                    for index in range(1, 16):
                        result = page.request.post(state['url']+'api/v1/row', headers=origin,
                            data={'tableId':item['tableId'],'action':'create','fields':{'name':f'Shot {index:02}',
                                'renderedVideo':f'/STASS/fixture.mp4#t={index}'}})
                        self.assertTrue(result.ok)
                    page.goto(state['url']+'?section=rewrites&manuscript='+item['draftId']+'&rewriteTab=motionStoryboard')
                    frame=page.frame_locator('iframe.rewrite-motion-table')
                    frame.locator('#tableTitle:text-is("Embedded Board")').wait_for()
                    expect(page.locator('iframe.rewrite-motion-table')).to_have_attribute('data-table-loaded','1')
                    player=page.locator('.rewrite-film-player video')
                    player.evaluate("v=>{Object.defineProperty(v,'currentTime',{value:12.4});v.dispatchEvent(new Event('seeked'));}")
                    playing=frame.locator('#rows tr[aria-current=step]')
                    expect(playing).to_contain_text('Shot 12')
                    page.locator('[data-shot-jump]').click()
                    expect(playing).to_be_in_viewport()
                    page.locator('[data-player-jump]').click()
                    expect(player).to_be_in_viewport()
                    first_shot = frame.locator('#rows tr[data-id]').first
                    feedback = first_shot.get_by_role('textbox', name='用户修改意见')
                    expect(feedback).to_have_value('')
                    table_scroll = frame.locator('.rewrite-table-embed .table-scroll')
                    iframe = page.locator('iframe.rewrite-motion-table')
                    page.wait_for_function('''() => {
                        const frame = document.querySelector('iframe.rewrite-motion-table');
                        const table = frame.contentDocument.querySelector('.table-scroll');
                        return frame.clientHeight > 1000 && frame.contentDocument.scrollingElement.scrollHeight === frame.clientHeight
                            && table.scrollHeight === table.clientHeight;
                    }''')
                    full_height = iframe.bounding_box()['height']
                    search = frame.locator('#searchInput')
                    search.fill('Fixture community')
                    expect(frame.locator('#rows tr[data-id]')).to_have_count(1)
                    page.wait_for_function('(height) => document.querySelector("iframe.rewrite-motion-table").offsetHeight < height', arg=full_height)
                    search.fill('')
                    expect(frame.locator('#rows tr[data-id]')).to_have_count(16)
                    last_shot = frame.locator('#rows tr[data-id]').last
                    last_shot.locator('[data-action=edit]').click()
                    dialog = frame.locator('#rowDialog')
                    dialog_box = dialog.bounding_box()
                    self.assertGreaterEqual(dialog_box['y'], 0)
                    self.assertLessEqual(dialog_box['y'] + dialog_box['height'], page.viewport_size['height'])
                    dialog.locator('.close-modal').click()
                    expect(first_shot.locator('[data-note-direct] button')).to_have_count(0)
                    feedback.fill('\n换一个构图\n\n保留字幕')
                    expect(frame.locator('#notice')).to_have_text('已保存用户修改意见')
                    expect(feedback).to_be_focused()
                    page.reload()
                    expect(feedback).to_have_value('\n换一个构图\n\n保留字幕')
                    page.route('**/api/v1/row', lambda route: route.fulfill(status=500, content_type='application/json', body='{"error":"fixture save failure"}'))
                    feedback.fill('保留字幕\n换一个构图')
                    expect(frame.get_by_text('fixture save failure',exact=False)).to_be_visible()
                    expect(feedback).to_have_value('保留字幕\n换一个构图')
                    page.unroute('**/api/v1/row')
                    feedback.blur()
                    expect(frame.locator('#notice')).to_have_text('已保存用户修改意见')
                    feedback.fill('切换前保存')
                    page.get_by_role('tab',name='文案版本').click()
                    page.locator('iframe.rewrite-motion-table').wait_for(state='detached')
                    page.get_by_role('tab',name='motion分镜表').click()
                    expect(feedback).to_have_value('切换前保存')
                    page.set_viewport_size({'width':390, 'height':844})
                    self.assertEqual(page.evaluate('document.documentElement.scrollWidth'),390)
                    self.assertGreaterEqual(table_scroll.bounding_box()['width'],250)
                    self.assertTrue(table_scroll.evaluate('(el) => el.scrollWidth > el.clientWidth'))
                    page.set_viewport_size({'width':1280, 'height':720})
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
                    navigation = page.locator('.workspace-nav-links')
                    expect(navigation.locator(':scope > *')).to_have_count(11)
                    expect(navigation.get_by_role('link', name='首页', exact=True)).to_have_count(0)
                    self.assertEqual(navigation.locator(':scope > *').all_text_contents()[:3], ['表格', '拉片', '报表'])
                    for label in ('设置 · 组件与技能', '关于'):
                        self.assertTrue(page.get_by_role('link', name=label, exact=True).is_visible())
                    self.assertEqual(page.locator('[aria-current=page]').inner_text(), '浏览器用户')
                    self.assertEqual(page.evaluate('document.documentElement.scrollWidth'), 320)
                    page.get_by_text('暂无浏览器用户，请先创建。',exact=True).wait_for()
                    self.assertEqual(failed_assets,[])
                    self.assertEqual(errors,[])
                    browser.close()
            finally: stop(root)



    def test_rating_filter_and_sort_browser(self):
        from playwright.sync_api import sync_playwright, expect
        with tempfile.TemporaryDirectory(prefix='STASS score ') as temporary:
            root=Path(temporary)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
            state=register_development(root,Path(__file__).parent,sys.executable,port)
            start(root)
            try:
                with sync_playwright() as pw:
                    browser=pw.chromium.launch(headless=True)
                    page=browser.new_page()
                    errors=[]
                    page.on('pageerror',lambda error: errors.append(str(error)))
                    page.goto(state['url'])
                    origin={'Origin':state['url'].removesuffix('/STASS/')}
                    def post(path,body):
                        response=page.request.post(state['url']+'api/v1/'+path,headers=origin,data=body)
                        self.assertEqual(response.status,200,response.text())
                        return response.json()
                    base=post('workspace',{'action':'create','level':'knowledge_base','name':'Rating test'})
                    project=post('workspace',{'action':'create','level':'project','knowledgeBaseId':base['id'],'name':'Ratings'})
                    table=post('workspace',{'action':'create','level':'table','knowledgeBaseId':base['id'],'projectId':project['id'],'name':'Rating table'})
                    tid=table['id']
                    post('define',{'tableId':tid,'fields':[{'name':'name','type':'text','label':'名称'}]})
                    for name,score in [('A',None),('B',0.5),('C',4.5),('D',4.5),('E',5)]:
                        row=post('row',{'tableId':tid,'action':'create','fields':{'name':name}})
                        if score is not None: post('review',{'tableId':tid,'rowId':row['id'],'score':score})
                    page.goto(state['url']+'?table='+tid)
                    rows=page.locator('#rows tr[data-id]')
                    expect(rows).to_have_count(5)
                    scores=lambda: rows.locator('.table-rating').evaluate_all('(els)=>els.map(e=>Number(e.getAttribute("aria-valuenow")))')
                    sort=page.get_by_role('button',name='评分排序',exact=True)
                    sort.click(); self.assertEqual(scores(),[5,4.5,4.5,0.5,0])
                    expect(sort.locator('..')).to_have_attribute('aria-sort','descending')
                    sort.press('Enter'); self.assertEqual(scores(),[0.5,4.5,4.5,5,0])
                    page.locator('.schema-filter-panel summary').click()
                    status=page.get_by_role('combobox',name='评分状态',exact=True)
                    minimum=page.get_by_role('spinbutton',name='评分最低分')
                    maximum=page.get_by_role('spinbutton',name='评分最高分')
                    status.select_option('unscored'); expect(rows).to_have_count(1)
                    status.select_option('scored'); expect(rows).to_have_count(4)
                    minimum.fill('4.5'); maximum.fill('4.5'); expect(rows).to_have_count(2)
                    page.locator('#searchInput').fill('C'); expect(rows).to_have_count(1)
                    page.locator('#searchInput').fill('')
                    minimum.fill('5'); expect(rows).to_have_count(0)
                    expect(page.locator('#schemaFilterError')).to_contain_text('最低分不能大于最高分')
                    minimum.fill('4.5')
                    # Saving a score outside the active range immediately removes the row.
                    rows.first.get_by_role('slider',name='评分',exact=True).press('Home')
                    expect(rows).to_have_count(1)
                    page.locator('[data-clear-rating]').click(); expect(rows).to_have_count(5)
                    status.select_option('unscored'); expect(rows).to_have_count(2)
                    page.locator('#clearFilters').click(); expect(rows).to_have_count(5)
                    expect(status).to_have_value('')
                    minimum.fill('0.5'); maximum.fill('0.5'); expect(rows).to_have_count(1)
                    page.reload(); expect(rows).to_have_count(5)
                    page.set_viewport_size({'width':390,'height':844})
                    page.locator('.schema-filter-panel summary').click()
                    expect(page.get_by_role('spinbutton',name='评分最低分')).to_be_visible()
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),390)
                    self.assertEqual(errors,[])
                    browser.close()
            finally: stop(root)

    def test_table_pagination_expands_rows_in_the_page(self):
        from playwright.sync_api import sync_playwright, expect

        with tempfile.TemporaryDirectory(prefix='STASS pagination ') as temporary:
            root = Path(temporary)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            state = register_development(root, Path(__file__).parent, sys.executable, port)
            start(root)
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True)
                    page = browser.new_page(viewport={'width': 390, 'height': 600})
                    origin = {'Origin': state['url'].removesuffix('/STASS/')}

                    def post(path, body):
                        response = page.request.post(state['url'] + 'api/v1/' + path, headers=origin, data=body)
                        self.assertEqual(response.status, 200, response.text())
                        return response.json()

                    base = post('workspace', {'action': 'create', 'level': 'knowledge_base', 'name': 'Pagination'})
                    project = post('workspace', {'action': 'create', 'level': 'project',
                                                 'knowledgeBaseId': base['id'], 'name': 'Fixtures'})
                    table = post('workspace', {'action': 'create', 'level': 'table',
                                               'knowledgeBaseId': base['id'], 'projectId': project['id'], 'name': '105 rows'})
                    table_id = table['id']
                    post('define', {'tableId': table_id, 'fields': [{'name': 'sequence', 'type': 'number', 'label': '镜号'},
                                                                   {'name': 'name', 'type': 'text', 'label': '名称'}]})
                    records = [post('row', {'tableId': table_id, 'action': 'create',
                                            'fields': {'sequence': i, 'name': f'Record {i:03}'}})
                               for i in range(1, 106)]
                    page.goto(state['url'] + '?table=' + table_id)
                    rows = page.locator('#rows tr[data-id]')
                    size = page.get_by_role('combobox', name='每页', exact=True)
                    next_page = page.get_by_role('button', name='下一页', exact=True)
                    back = page.get_by_role('button', name='上一页', exact=True)
                    status = page.locator('#tablePageStatus')
                    expect(size).to_have_value('50')
                    self.assertEqual(size.locator('option').all_text_contents(), ['20 行', '50 行', '100 行'])
                    expect(rows).to_have_count(50)
                    expect(rows.last).to_contain_text('Record 050')
                    expect(back).to_be_disabled()
                    layout = page.locator('.table-scroll').evaluate('''el => ({
                        tall: el.clientHeight > innerHeight,
                        full: el.clientHeight === el.scrollHeight,
                        scrollbar: getComputedStyle(el).scrollbarWidth,
                        width: document.documentElement.scrollWidth,
                    })''')
                    self.assertEqual(layout, {'tall': True, 'full': True, 'scrollbar': 'none', 'width': 390})
                    right = page.get_by_role('button', name='向右浏览列')
                    right.click()
                    self.assertGreater(page.locator('.table-scroll').evaluate('el => el.scrollLeft'), 0)

                    next_page.click()
                    expect(rows.first).to_contain_text('Record 051')
                    next_page.click()
                    expect(rows).to_have_count(5)
                    expect(next_page).to_be_disabled()
                    expect(status).to_have_text('第 3 / 3 页')
                    back.click()
                    expect(rows).to_have_count(50)
                    size.select_option('20')
                    expect(rows).to_have_count(20)
                    expect(status).to_have_text('第 1 / 6 页')
                    self.assertTrue(page.evaluate('id => window.tableRowPage(id, true)', records[104]['id']))
                    expect(status).to_have_text('第 6 / 6 页')
                    expect(rows.last).to_contain_text('Record 105')
                    page.locator('#searchInput').fill('Record 0')
                    expect(status).to_have_text('第 1 / 5 页')
                    next_page.click()
                    page.get_by_role('button', name='评分排序', exact=True).press('Enter')
                    expect(status).to_have_text('第 1 / 5 页')
                    page.locator('#searchInput').fill('没有匹配的记录')
                    expect(rows).to_have_count(0)
                    expect(next_page).to_be_disabled()
                    page.locator('#clearFilters').click()
                    size.select_option('100')
                    expect(rows).to_have_count(100)
                    next_page.click()
                    expect(rows).to_have_count(5)
                    page.reload()
                    expect(size).to_have_value('50')
                    expect(rows).to_have_count(50)
                    browser.close()
            finally:
                stop(root)


    def test_sidebar_search_date_ranges_and_order(self):
        import os
        import time
        from playwright.sync_api import sync_playwright, expect

        with tempfile.TemporaryDirectory(prefix='STASS directory ') as temporary:
            root = Path(temporary)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            state = register_development(root, Path(__file__).parent, sys.executable, port)
            start(root)
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True)
                    page = browser.new_page(viewport={'width': 1100, 'height': 650})
                    page.set_default_timeout(5000)
                    origin = {'Origin': state['url'].removesuffix('/STASS/')}

                    def post(path, body):
                        response = page.request.post(state['url'] + 'api/v1/' + path, headers=origin, data=body)
                        self.assertEqual(response.status, 200, response.text())
                        return response.json()

                    tables = {}
                    for base_name, project_name, records in [
                        ('工作台 A', '视频研究', [('精选近况', 4), ('精选历史', 800), ('培训记录', 140)]),
                        ('工作台 B', '课程策划', [('最新草稿', .5), ('当天记录', 15), ('归档甲', 50), ('归档乙', 400)]),
                    ]:
                        base = post('workspace', {'action': 'create', 'level': 'knowledge_base', 'name': base_name})
                        project = post('workspace', {'action': 'create', 'level': 'project',
                                                     'knowledgeBaseId': base['id'], 'name': project_name})
                        for name, hours in records:
                            table = post('workspace', {'action': 'create', 'level': 'table', 'name': name,
                                                       'description': 'Storyboard' if name == '精选近况' else '',
                                                       'knowledgeBaseId': base['id'], 'projectId': project['id']})
                            tables[name] = table['id']
                            stamp = time.time() - hours * 3600
                            os.utime(Path(state['dataRoot']) / 'tables' / (table['id'] + '.json'), (stamp, stamp))

                    page.goto(state['url'] + '?table=' + tables['精选历史'])
                    nav = page.locator('#tree')
                    search = page.get_by_role('searchbox', name='搜索表格')
                    age = page.get_by_role('combobox', name='最近修改范围')
                    order = page.get_by_role('combobox', name='目录排序')
                    count = page.locator('#tableTreeCount')
                    current = page.locator('#tableTitle')
                    expect(current).to_have_text('精选历史')
                    base_a = nav.get_by_role('button', name='工作台 A', exact=True)
                    base_a.click()
                    expect(base_a).to_have_attribute('aria-expanded', 'false')
                    filter_button = page.get_by_role('button', name='筛选表格目录', exact=True)
                    expect(search).to_be_hidden()
                    tree_top = nav.bounding_box()['y']
                    filter_button.hover()
                    search.hover()
                    expect(filter_button).to_have_attribute('aria-expanded', 'true')
                    self.assertEqual(nav.bounding_box()['y'], tree_top)
                    base_a.hover()
                    expect(search).to_be_hidden()
                    filter_button.press('Enter')
                    expect(search).to_be_focused()

                    for hours, matches in [('1', 1), ('8', 2), ('24', 3), ('72', 4), ('168', 5), ('720', 6)]:
                        age.select_option(hours)
                        expect(count).to_have_text(f'{matches} 张表')
                    expect(order).to_have_value('newest')
                    expect(nav.locator('.tree-select').first).to_have_text('工作台 B')
                    expect(current).to_have_text('精选历史')
                    expect(nav.get_by_role('button', name='精选历史', exact=True)).to_have_count(0)

                    search.fill('视频 STORYBOARD')
                    expect(count).to_have_text('1 张表')
                    expect(base_a).to_have_attribute('aria-expanded', 'true')
                    result = nav.get_by_role('button', name='精选近况', exact=True)
                    self.assertIn('修改于', result.get_attribute('title'))
                    result.click()
                    expect(current).to_have_text('精选近况')
                    expect(result).to_have_attribute('aria-current', 'page')
                    expect(search).to_be_hidden()
                    expect(filter_button).to_have_attribute('data-active', '')
                    filter_button.click()
                    search.fill('没有命中的关键词')
                    expect(nav.get_by_text('没有符合条件的表格')).to_be_visible()
                    page.locator('#tableTreeReset').click()
                    expect(search).to_be_focused()
                    expect(base_a).to_have_attribute('aria-expanded', 'false')
                    order.select_option('oldest')
                    expect(nav.locator('.tree-select').first).to_have_text('工作台 A')
                    base_a.click()
                    expect(nav.locator('.tree-select').nth(2)).to_have_text('精选历史')

                    filter_button.click()
                    age.select_option('1')
                    expect(count).to_have_text('1 张表')
                    page.evaluate("""tableId => api('/STASS/api/v1/row',
                        {tableId, action: 'create', fields: {title: 'Recent update'}})""", tables['精选历史'])
                    expect(count).to_have_text('2 张表')
                    expect(nav.get_by_role('button', name='精选历史', exact=True)).to_be_visible()
                    search.press('Escape')
                    expect(search).to_be_hidden()
                    expect(filter_button).to_be_focused()
                    expect(nav.get_by_role('button', name='精选历史', exact=True)).to_be_visible()
                    phone = browser.new_page(viewport={'width': 390, 'height': 700}, has_touch=True)
                    phone.goto(state['url'] + '?table=' + tables['精选历史'])
                    phone.locator('#openSidebar').tap()
                    phone_filter = phone.get_by_role('button', name='筛选表格目录', exact=True)
                    phone_filter.tap()
                    expect(phone.get_by_role('searchbox', name='搜索表格')).to_be_visible()
                    self.assertEqual(phone.evaluate('document.documentElement.scrollWidth'), 390)
                    phone_filter.tap()
                    expect(phone.get_by_role('searchbox', name='搜索表格')).to_be_hidden()
                    browser.close()
            finally:
                stop(root)


if __name__=='__main__':unittest.main()
