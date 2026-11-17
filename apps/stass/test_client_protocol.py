import asyncio
import unittest

from client import execute


class ProtocolTests(unittest.TestCase):
    def test_incompatible_server_is_refused_before_reading_or_sending_token(self):
        import httpx2
        requests = []
        def respond(request):
            requests.append(request)
            return httpx2.Response(200,json={'service':'STASS','instanceId':'expected','protocol':99})
        async def run():
            with self.assertRaisesRegex(ValueError,'Incompatible'):
                await execute({'url':'http://localhost:8080/STASS/', 'instanceId':'expected',
                               'tokenFile':'this-file-must-never-be-read'}, 'list',
                              transport=httpx2.MockTransport(respond))
        asyncio.run(run())
        self.assertEqual(len(requests),1)
        self.assertNotIn('authorization',requests[0].headers)


if __name__ == '__main__': unittest.main()
