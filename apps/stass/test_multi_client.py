import asyncio
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest

from client_auth import issue, revoke
from runtime_control import register_development, start, stop


class MultiClientTests(unittest.TestCase):
    def test_three_stdio_clients_share_data_and_revocation_is_immediate(self):
        from mcp import Client
        from mcp.client.stdio import StdioServerParameters
        from client import execute
        with tempfile.TemporaryDirectory(prefix='STASS 三宿主 ') as tmp:
            root = Path(tmp)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
            source = Path(__file__).parent
            register_development(root, source, sys.executable, port)
            profiles = {host:issue(root, host) for host in ('codex','claude','openclaw')}
            self.assertEqual(len({Path(p['tokenFile']).read_text() for p in profiles.values()}), 3)
            start(root)
            async def call(host, args):
                profile_path = root / 'config' / ('client-' + host + '.json')
                async with Client(StdioServerParameters(command=sys.executable, args=[str(source/'mcp_bridge.py'), '--profile', str(profile_path)])) as client:
                    tools = await client.list_tools()
                    self.assertTrue(tools.tools)
                    result = await client.call_tool('table_workspace', args)
                    self.assertFalse(result.is_error)
                    return json.loads(result.content[0].text)
            async def scenario():
                created = await call('codex', {'action':'create','level':'knowledge_base','name':'Original'})
                await call('claude', {'action':'rename','level':'knowledge_base','id':created['id'],'name':'Shared'})
                observed = await call('openclaw', {})
                self.assertEqual(observed['knowledgeBases'][0]['name'], 'Shared')
                old_token = Path(profiles['claude']['tokenFile']).read_text()
                revoke(root, 'claude')
                import httpx2
                async with httpx2.AsyncClient() as http:
                    response = await http.post(profiles['claude']['url']+'mcp',headers={'Authorization':'Bearer '+old_token},json={})
                    self.assertEqual(response.status_code,401)
                    response = await http.post(profiles['codex']['url']+'api/v1/tools/table_workspace',headers={'Authorization':'Bearer '+Path(profiles['codex']['tokenFile']).read_text()},json={})
                    self.assertEqual(response.status_code,403)
                _, result = await execute(profiles['openclaw'],'list')
                self.assertTrue(result['tools'])
            try:
                asyncio.run(scenario())
            finally:
                stop(root)


if __name__ == '__main__': unittest.main()
