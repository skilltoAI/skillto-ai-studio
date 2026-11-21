import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest


class ServiceTests(unittest.TestCase):
    def test_mcp_and_api_share_data_and_enforce_auth_origin_host(self):
        import httpx2
        with tempfile.TemporaryDirectory() as tmp:
            token=Path(tmp)/'token';token.write_text('fixture-'*8)
            os.environ.update(STASS_DATA_ROOT=tmp,STASS_TOKEN_FILE=str(token),STASS_ALLOWED_HOSTS='localhost:8080,192.168.3.55:8091',
                              SKILLTO_REPORT_CONFIG=str(Path(tmp) / 'reporting.json'))
            import service
            async def run():
                async with service.inner.router.lifespan_context(service.inner):
                    async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=service.app),base_url='http://localhost:8080') as client:
                        self.assertEqual((await client.post('/STASS/mcp',json={})).status_code,401)
                        self.assertEqual((await client.get('/STASS/health',headers={'Host':'evil.test'})).status_code,403)
                        self.assertEqual((await client.get('/STASS/health',headers={'Origin':'http://evil.test'})).status_code,403)
                        self.assertEqual((await client.get('/STASS/',headers={'Sec-Fetch-Site':'cross-site'})).status_code,403)
                        self.assertEqual((await client.post('/STASS/api/v1/workspace',json={})).status_code,403)
                        self.assertEqual((await client.get('/STASS/api/v1/pair-code')).status_code,401)
                        empty_reports = await client.get('/STASS/api/v1/reports/catalog')
                        self.assertEqual(empty_reports.status_code, 200)
                        self.assertEqual(empty_reports.json()['knowledgeBases'], [])
                        self.assertFalse(empty_reports.json()['configured'])
                        links = '/STASS/api/v1/document-links'
                        self.assertEqual((await client.get(links)).json(), [])
                        local = {'Origin': 'http://localhost:8080'}
                        response = await client.post(links, headers=local, json={
                            'action': 'add', 'title': 'Example', 'url': 'https://example.test/doc'})
                        self.assertEqual(response.status_code, 200, response.text)
                        saved = (await client.get(links)).json()
                        self.assertEqual(saved[0]['url'], 'https://example.test/doc')
                        unsafe = await client.post(links, headers=local, json={
                            'action': 'add', 'title': 'Example', 'url': 'javascript:alert(1)'})
                        self.assertEqual(unsafe.status_code, 400)
                        removed = await client.post(links, headers=local, json={'action': 'remove', 'id': saved[0]['id']})
                        self.assertEqual(removed.json(), [])
                        async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=service.app,client=('192.168.3.60',32100)),base_url='http://localhost:8080') as remote:
                            denied=await remote.get('/STASS/',headers={'X-Forwarded-For':'127.0.0.1'})
                            self.assertEqual(denied.headers['location'],'/STASS/pair')
                        health=(await client.get('/STASS/health')).json()
                        self.assertEqual(health['service'],'STASS');self.assertTrue(health['instanceId'])
                        headers={'Authorization':'Bearer '+'fixture-'*8,'Accept':'application/json, text/event-stream'}
                        response=await client.post('/STASS/mcp',headers=headers,json={'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'test','version':'1'}}})
                        self.assertEqual(response.status_code,200)
                        response=await client.post('/STASS/mcp',headers=headers,json={'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'table_workspace','arguments':{'action':'create','level':'knowledge_base','name':'MCP test'}}})
                        result=response.json()['result'];self.assertFalse(result.get('isError'))
                        ident=json.loads(result['content'][0]['text'])['id']
                        response=await client.post('/STASS/api/v1/tools/table_workspace',headers=headers,json={})
                        self.assertEqual(response.status_code,200)
                        self.assertEqual(response.json()['result']['knowledgeBases'][0]['id'],ident)
                        self.assertTrue((Path(tmp)/'catalog.json').is_file())
                        async def call_tool(name, arguments):
                            response = await client.post('/STASS/mcp',headers=headers,json={
                                'jsonrpc':'2.0','id':4,'method':'tools/call',
                                'params':{'name':name,'arguments':arguments}})
                            result = response.json()['result']
                            self.assertFalse(result.get('isError'), result)
                            return json.loads(result['content'][0]['text'])
                        project = await call_tool('table_workspace',{'action':'create','level':'project','knowledgeBaseId':ident,'name':'Ratings'})
                        table = await call_tool('table_workspace',{'action':'create','level':'table','knowledgeBaseId':ident,'projectId':project['id'],'name':'Ratings'})
                        row = await call_tool('table_save_row',{'tableId':table['id'],'fields':{'title':'Example'}})
                        rated = await call_tool('table_review',{'tableId':table['id'],'rowId':row['id'],'score':2.5,'note':'Keep note'})
                        self.assertEqual(rated['rating'],{'score':2.5,'note':'Keep note'})
                        queried = await call_tool('table_query',{'tableId':table['id'],'filters':[{'field':'score','operator':'between','value':[2,3]}]})
                        self.assertEqual(queried['rows'][0]['rating']['score'],2.5)
                        asset_batch = {'action':'ingest','source':{'url':'https://my.feishu.cn/wiki/PublicExample','title':'Example','access':'anonymous'},
                            'items':[{'library':'red-white','sourceBlockId':'Block1','title':'Example','prompt':'Complete prompt',
                                'filename':'example.mp4','fileToken':'File1','playback':'source-page'}]}
                        dry = await call_tool('ai_assets_action',{'arguments':{**asset_batch,'dryRun':True}})
                        self.assertTrue(dry['dryRun'])
                        self.assertFalse((Path(tmp)/'ai-assets.json').exists())
                        await call_tool('ai_assets_action',{'arguments':asset_batch})
                        assets = await call_tool('ai_assets_action',{'arguments':{'action':'catalog'}})
                        catalog = (await client.get('/STASS/api/v1/ai-assets/catalog',headers=headers)).json()
                        self.assertEqual(assets,catalog)
                        self.assertEqual(catalog['items'][0]['prompt'],'Complete prompt')
                        from unittest.mock import patch
                        import io
                        class Video(io.BytesIO):
                            status=206
                            headers={'Content-Type':'video/mp4','Content-Length':'8','Content-Range':'bytes 0-7/100'}
                        upstream=Video(b'ftypdata')
                        media_url='/STASS/api/v1/ai-assets/media/'+catalog['items'][0]['id']
                        with patch.object(service.ai_asset_media,'open_media',return_value=upstream) as open_media:
                            video=await client.get(media_url+'?download=1',headers={**headers,'Range':'bytes=0-7'})
                            self.assertEqual(video.status_code,206)
                            self.assertEqual(video.content,b'ftypdata')
                            self.assertEqual(video.headers['content-range'],'bytes 0-7/100')
                            self.assertIn('attachment;',video.headers['content-disposition'])
                            self.assertTrue(upstream.closed)
                            self.assertEqual(open_media.call_args.args[1],'bytes=0-7')
                            denied=await client.get(media_url,headers={'Sec-Fetch-Site':'cross-site'})
                            self.assertEqual(denied.status_code,403)
                        with patch.object(service.ai_asset_media,'open_media',side_effect=ValueError('private upstream details')):
                            failed=await client.get(media_url,headers=headers)
                            self.assertEqual(failed.status_code,502)
                            self.assertNotIn('private upstream details',failed.text)
                        response=await client.post('http://192.168.3.55:8091/STASS/mcp',headers=headers,json={'jsonrpc':'2.0','id':3,'method':'tools/list'})
                        self.assertEqual(response.status_code,200)
                        self.assertTrue(response.json()['result']['tools'])
            asyncio.run(run())


if __name__ == '__main__':unittest.main()
