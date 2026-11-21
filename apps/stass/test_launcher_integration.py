import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest

from runtime_control import register_development,stop


class LauncherTests(unittest.TestCase):
    def test_built_gui_exe_manages_shared_stass_instance(self):
        binary=Path(os.environ.get('STASS_LAUNCHER_EXE',Path(__file__).resolve().parents[2]/'runtime/Skillto.ai Studio.exe'))
        if not binary.is_file(): self.skipTest('Build the Windows launcher before binary integration testing')
        with tempfile.TemporaryDirectory(prefix='STASS 启动器 ') as temp:
            root=Path(temp)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            state=register_development(root,Path(__file__).parent,sys.executable,port)
            result=root/'receipt.json'
            common=[str(binary),'--config',str(root/'config/installation.json'),'--headless','--no-browser','--quiet-errors','--result-file',str(result)]
            try:
                for expected in ('started','reused'):
                    process=subprocess.run(common,timeout=45)
                    receipt=json.loads(result.read_text())
                    self.assertEqual(process.returncode,0,receipt)
                    self.assertEqual(receipt['action'],expected)
                    self.assertEqual(receipt['url'],state['url'])
                process=subprocess.run(common+['--stop'],timeout=45)
                self.assertEqual(process.returncode,0,json.loads(result.read_text()))
                self.assertEqual(json.loads(result.read_text())['action'],'stopped')
            finally: stop(root)


if __name__=='__main__':unittest.main()
