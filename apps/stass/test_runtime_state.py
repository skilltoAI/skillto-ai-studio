import concurrent.futures
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from runtime_state import RuntimeState, installation_lock


class RuntimeStateTests(unittest.TestCase):
    def test_three_hosts_initialize_one_instance(self):
        with tempfile.TemporaryDirectory(prefix='STASS 中文 ') as folder:
            root = Path(folder) / '共享 程序'
            code = ('import json,sys; from runtime_state import RuntimeState; '
                    'print(json.dumps(RuntimeState(sys.argv[1]).initialize()))')
            def initialize(_):
                return json.loads(subprocess.check_output(
                    [sys.executable, '-c', code, str(root)], cwd=Path(__file__).parent))
            with concurrent.futures.ThreadPoolExecutor(3) as pool:
                results = list(pool.map(initialize, range(3)))
            self.assertEqual(len({row['instanceId'] for row in results}), 1)
            self.assertEqual(len({row['dataRoot'] for row in results}), 1)
            self.assertEqual(RuntimeState(root).read(), results[0])
            with self.assertRaisesRegex(ValueError, 'migration'):
                RuntimeState(root).initialize(Path(folder) / 'different')

    def test_existing_data_is_never_adopted_or_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder) / 'existing'
            data.mkdir()
            original = data / 'catalog.json'
            original.write_text('{"preserve":true}')
            with self.assertRaises(ValueError):
                RuntimeState(Path(folder) / 'app').initialize(data)
            self.assertEqual(original.read_text(), '{"preserve":true}')

    def test_competing_process_times_out(self):
        with tempfile.TemporaryDirectory() as folder:
            with installation_lock(folder):
                result = subprocess.run([sys.executable, '-c',
                    'import sys; from runtime_state import installation_lock; '
                    '\nwith installation_lock(sys.argv[1], 50): pass', folder],
                    cwd=Path(__file__).parent, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b'TimeoutError', result.stderr)


if __name__ == '__main__':
    unittest.main()
