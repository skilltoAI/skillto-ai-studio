import concurrent.futures
import hashlib
import json
from pathlib import Path
import socket
import tempfile
import unittest

from release_gate import stage, select_offline, verify_selected
from runtime_state import RuntimeState


def fixture(folder, version='1.0.0', schema=1):
    folder.mkdir()
    files = {}
    for name in ('program/service.py','program/supervisor.py','runtime/python.exe','Skillto.ai Studio.exe'):
        path = folder / name
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_bytes(('fixture-only: '+version+name).encode())
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {'format':1,'version':version,'commit':'a'*40,'dataSchema':schema,'protocol':1,'files':files}
    path = folder / 'release.json'
    path.write_text(json.dumps(manifest), encoding='utf-8')
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='STASS 更新 空格 ')
        self.base = Path(self.temp.name)
        self.runtime = RuntimeState(self.base/'shared')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            port = sock.getsockname()[1]
        self.runtime.initialize(port=port)

    def tearDown(self): self.temp.cleanup()

    def test_source_pull_does_not_change_installed_snapshot_or_data(self):
        source = self.base/'source'
        digest = fixture(source)
        key = stage(self.runtime.root, source, digest)
        state = select_offline(self.runtime.root,key,digest,0)
        data = Path(state['dataRoot'])/'user.json'
        data.write_bytes(b'preserve history and media references')
        (source/'program/service.py').write_text('changed by another checkout')
        self.assertEqual(verify_selected(self.runtime,self.runtime.read())['version'],'1.0.0')
        self.assertEqual(data.read_bytes(),b'preserve history and media references')
        self.assertEqual(self.runtime.read()['generation'],1)

    def test_two_updaters_cannot_overwrite_each_others_selection(self):
        candidates = []
        for number in (1,2):
            folder = self.base/str(number)
            digest = fixture(folder, f'1.0.{number}')
            candidates.append((stage(self.runtime.root,folder,digest),digest))
        def update(candidate):
            try:
                select_offline(self.runtime.root,*candidate,0)
                return 'selected'
            except ValueError as exc:
                self.assertIn('Stale', str(exc))
                return 'stale'
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            self.assertCountEqual(list(pool.map(update,candidates)),['selected','stale'])
        self.assertEqual(self.runtime.read()['generation'],1)

    def test_schema_change_and_downgrade_leave_state_and_data_unchanged(self):
        digest = fixture(self.base/'initial','2.0.0')
        key = stage(self.runtime.root,self.base/'initial',digest)
        state = select_offline(self.runtime.root,key,digest,0)
        for version,schema in [('3.0.0',2),('1.0.0',1),('2.0.0',1)]:
            directory = self.base/(version+'-'+str(schema))
            candidate_digest = fixture(directory,version,schema)
            if version == '2.0.0':
                manifest = json.loads((directory/'release.json').read_text())
                manifest['commit']='b'*40
                (directory/'release.json').write_text(json.dumps(manifest))
                candidate_digest=hashlib.sha256((directory/'release.json').read_bytes()).hexdigest()
            candidate = stage(self.runtime.root,directory,candidate_digest)
            with self.assertRaises(ValueError):
                select_offline(self.runtime.root,candidate,candidate_digest,1)
            self.assertEqual(self.runtime.read(),state)

    def test_tampered_or_unlisted_payload_is_refused(self):
        digest=fixture(self.base/'source')
        key=stage(self.runtime.root,self.base/'source',digest)
        state=select_offline(self.runtime.root,key,digest,0)
        payload=self.runtime.root/'versions'/key/'program/service.py'
        payload.write_text('modified installed code')
        with self.assertRaisesRegex(ValueError,'digest mismatch'):
            verify_selected(self.runtime,state)
        (self.base/'source'/'extra.txt').write_text('unlisted')
        with self.assertRaisesRegex(ValueError,'Unlisted'):
            stage(self.runtime.root,self.base/'source',digest)


if __name__ == '__main__': unittest.main()
