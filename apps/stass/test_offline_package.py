"""Smoke test run against the assembled package and its embedded interpreter."""
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
import urllib.request

from release_gate import sha256


class OfflinePackageTests(unittest.TestCase):
    def test_install_reuse_and_exe_shutdown_with_embedded_python(self):
        value = os.environ.get('STASS_TEST_OFFLINE_PACKAGE')
        if not value:
            self.skipTest('Set STASS_TEST_OFFLINE_PACKAGE to the assembled package')
        package = Path(value).resolve(strict=True)
        digest = sha256(package/'release.json')
        with tempfile.TemporaryDirectory(prefix='STASS 离线 安装 ') as temp:
            root = Path(temp)
            with socket.socket() as listener:
                listener.bind(('127.0.0.1',0))
                port = listener.getsockname()[1]
            command = ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
                       str(package/'Install.ps1'),'-Root',str(root),'-Port',str(port),'-ManifestSha256',digest]
            first = json.loads(subprocess.check_output(command,timeout=90).decode('utf-8'))
            launcher = Path(first['launcher'])
            try:
                token = (root/'config/admin.token').read_text()
                request = urllib.request.Request(first['url']+'api/v1/tools/table_workspace',
                    data=b'{"action":"create","level":"knowledge_base","name":"Offline proof"}',
                    headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
                with urllib.request.urlopen(request,timeout=5) as response:
                    self.assertEqual(response.status,200)
                second = json.loads(subprocess.check_output(command,timeout=90).decode('utf-8'))
                self.assertEqual(first['instanceId'],second['instanceId'])
                self.assertEqual(second['action'],'reused')
                self.assertEqual(len(list((root/'versions').iterdir())),1)
                self.assertIn('Offline proof',(root/'data/catalog.json').read_text(encoding='utf-8'))
            finally:
                subprocess.run([str(launcher),'--config',str(root/'config/installation.json'),
                                '--quiet-errors','--stop'],check=True,timeout=50)


if __name__ == '__main__': unittest.main()
