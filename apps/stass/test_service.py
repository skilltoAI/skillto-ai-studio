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
            os.environ.update(STASS_DATA_ROOT=tmp,STASS_TOKEN_FILE=str(token),STASS_ALLOWED_HOSTS='localhost:8080,192.168.3.55:8091')
            import service
            async def run():
                async with service.inner.router.lifespan_context(service.inner):
                    async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=service.app),base_url='http://localhost:8080') as client:
                        self.assertEqual((await client.post('/STASS/mcp',json={})).status_code,401)
                        self.assertEqual((await client.get('/STASS/health',headers={'Host':'evil.test'})).status_code,403)
                        self.assertEqual((await client.get('/STASS/health',headers={'Origin':'http://evil.test'})).status_code,403)
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
                        response=await client.post('http://192.168.3.55:8091/STASS/mcp',headers=headers,json={'jsonrpc':'2.0','id':3,'method':'tools/list'})
                        self.assertEqual(response.status_code,200)
                        self.assertTrue(response.json()['result']['tools'])
            asyncio.run(run())


if __name__ == '__main__':unittest.main()
