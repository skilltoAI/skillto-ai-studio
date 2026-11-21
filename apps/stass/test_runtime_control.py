import concurrent.futures
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest

from runtime_control import health, register_development, start, stop


class LifecycleTests(unittest.TestCase):
    def test_three_processes_reuse_service_and_data_survives_restart(self):
        with tempfile.TemporaryDirectory(prefix='STASS 服务 空格 ') as temporary:
            with socket.socket() as reservation:
                reservation.bind(('127.0.0.1', 0))
                port = reservation.getsockname()[1]
            root = Path(temporary)
            source = Path(__file__).parent
            state = register_development(root, source, sys.executable, port)
            def launch(_):
                return json.loads(subprocess.check_output([sys.executable,
                    str(source / 'runtime_control.py'), 'start', '--root', str(root)]))
            try:
                with concurrent.futures.ThreadPoolExecutor(3) as pool:
                    results = list(pool.map(launch, range(3)))
                self.assertEqual(len({r['pid'] for r in results}), 1)
                self.assertEqual(sum(r['action'] == 'started' for r in results), 1)
                self.assertEqual(health(state)['instanceId'], state['instanceId'])
                import urllib.request
                token = (root / 'config/admin.token').read_text()
                request = urllib.request.Request(state['url'] + 'api/v1/tools/table_workspace',
                    data=json.dumps({'action':'create','level':'knowledge_base','name':'Shared lifecycle'}).encode(),
                    headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
                with urllib.request.urlopen(request) as response:
                    ident = json.load(response)['result']['id']
                self.assertEqual(stop(root)['action'], 'stopped')
                start(root)
                request.data = b'{}'
                with urllib.request.urlopen(request) as response:
                    self.assertEqual(json.load(response)['result']['knowledgeBases'][0]['id'], ident)
            finally:
                stop(root)

    def test_unrelated_port_is_not_reused_or_stopped(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        class Other(BaseHTTPRequestHandler):
            def do_GET(self):
                body = b'{"service":"unrelated"}'
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(('127.0.0.1',0),Other)
        worker = threading.Thread(target=server.serve_forever)
        worker.start()
        try:
            with tempfile.TemporaryDirectory() as root:
                register_development(root, Path(__file__).parent, sys.executable, server.server_port)
                for operation in (start, stop):
                    with self.assertRaisesRegex(ValueError, 'another service'):
                        operation(root)
        finally:
            server.shutdown()
            server.server_close()
            worker.join()


if __name__ == '__main__': unittest.main()
