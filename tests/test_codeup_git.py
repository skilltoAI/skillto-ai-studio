"""Offline credential isolation and Git command contracts; no real passwords."""
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('codeup_git', Path(__file__).parents[1] / 'scripts/codeup_git.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CodeupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.key = Path(self.temp.name) / 'key with spaces'
        self.key.write_text('test fixture only')
        self.settings = {}
        for scope in ('fetch', 'push'):
            self.settings[scope] = dict(BASE_URL='https://codeup.aliyun.com/org/repo.git',
                                       USERNAME='reader' if scope == 'fetch' else 'git',
                                       PASSWORD='synthetic-' + scope,
                                       SSH_KEY_FILE=str(self.key),
                                       AUTH_MODE='https-password' if scope == 'fetch' else 'ssh')
        p = patch.object(module, 'setting', side_effect=lambda s, k: self.settings[s][k])
        p.start()
        self.addCleanup(p.stop)

    def test_fetch_no_password_in_arguments_or_push_environment(self):
        with patch.dict(os.environ, {'CODEUP_PUSH_PASSWORD':'different-secret', 'GIT_TRACE_CURL':'1'}):
            args, env, _ = module.command('fetch', 'fetch')
        self.assertNotIn('synthetic-fetch', ' '.join(args))
        self.assertEqual(env['CODEUP_FETCH_PASSWORD'], 'synthetic-fetch')
        self.assertFalse(any(k.startswith('CODEUP_PUSH_') for k in env))
        self.assertNotIn('GIT_TRACE_CURL', env)
        self.assertIn('credential.helper=', args)
        self.assertIn('+refs/heads/*:refs/remotes/codeup/*', args)

    def test_ssh_explicit_key_and_no_fallback(self):
        args, env, _ = module.command('push', 'probe')
        self.assertIn('git@codeup.aliyun.com:org/repo.git', args)
        self.assertIn(self.key.as_posix(), env['GIT_SSH_COMMAND'])
        self.assertIn('StrictHostKeyChecking=yes', env['GIT_SSH_COMMAND'])
        self.assertIn('IdentitiesOnly=yes', env['GIT_SSH_COMMAND'])
        self.assertIn('-F none', env['GIT_SSH_COMMAND'])
        self.assertNotIn('push', args)

    def test_missing_fetch_password_does_not_use_push_password(self):
        self.settings['fetch']['PASSWORD'] = ''
        with self.assertRaisesRegex(ValueError, 'FETCH_PASSWORD'):
            module.command('fetch', 'probe')

    def test_helper_exact_repository_only(self):
        for path, expected in [('org/repo.git', 0), ('org/other.git', 1)]:
            output = io.StringIO()
            with patch('sys.stdin', io.StringIO('protocol=https\nhost=codeup.aliyun.com\npath='+path+'\n\n')), patch('sys.stdout', output):
                result = module.credential('fetch', 'get')
            self.assertEqual(result, expected)
            self.assertEqual('synthetic-fetch' in output.getvalue(), expected == 0)

    def test_helper_does_not_persist_credentials(self):
        output = io.StringIO()
        with patch('sys.stdin', io.StringIO()), patch('sys.stdout', output):
            self.assertEqual(module.credential('fetch', 'store'), 0)
            self.assertEqual(module.credential('fetch', 'erase'), 0)
        self.assertEqual(output.getvalue(), '')

    def test_credentials_in_url_rejected(self):
        self.settings['fetch']['BASE_URL'] = 'https://user:example@codeup.aliyun.com/org/repo.git'
        with self.assertRaisesRegex(ValueError, 'credential-free'):
            module.command('fetch', 'probe')

    def test_public_key_file_not_private_key(self):
        self.settings['push']['SSH_KEY_FILE'] = str(self.key) + '.pub'
        with self.assertRaisesRegex(ValueError, 'private-key'):
            module.command('push', 'probe')

    def test_operation_cannot_cross_scope(self):
        with self.assertRaisesRegex(ValueError, 'do not match'):
            module.command('fetch', 'push', 'codex/example')
        with self.assertRaisesRegex(ValueError, 'do not match'):
            module.command('push', 'fetch')

    def test_no_main_or_delete_push(self):
        with self.assertRaises(ValueError):
            module.command('push', 'push', 'main')
        with self.assertRaises(ValueError):
            module.command('push', 'push', ':main')

    def test_clone_uses_fetch_scope(self):
        args, env, _ = module.command('fetch', 'clone', str(Path(self.temp.name)/'clone'))
        self.assertIn('clone', args)
        self.assertNotIn('GIT_SSH_COMMAND', env)


if __name__ == '__main__':
    unittest.main()
