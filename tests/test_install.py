"""Exercise installation side effects using isolated temporary directories."""
from contextlib import redirect_stdout
from io import StringIO
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import install


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='skillto-install-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo with spaces'
        self.destination = self.root / 'installed skills'
        for name in ('alpha', 'beta'):
            folder = self.repo / 'skills' / name
            folder.mkdir(parents=True)
            (folder / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: Test skill.\n---\n', encoding='utf-8')
        self.output = StringIO()
        self.capture = redirect_stdout(self.output)
        self.capture.__enter__()
        self.addCleanup(self.capture.__exit__, None, None, None)

    def run_install(self, skill='all', **kwargs):
        return install.install(self.destination, skill, repo_root=self.repo, **kwargs)

    def test_copies_siblings_resources_and_filters_local_state(self):
        source = self.repo / 'skills' / 'alpha'
        kept = {'scripts/helper.py': b'print("ok")\n', 'assets/brand.png': b'\x89PNG\x00test',
                'references/cookie-setup.md': b'Set up an authorized session.',
                'scripts/windows/winres/logo.png': b'brand'}
        omitted = ['scripts/__pycache__/cache.pyc', 'runtime/profile.json', '.env',
                   'auth.key', 'douyin-cookie.txt', 'cookie-store.json', 'local.sqlite3',
                   'SkillToTable.exe', 'launcher.local.json', 'build.syso',
                   'runtime.local.json', 'compose.env', 'assets/old.js.bak',
                   '.cache/state.json', '.playwright-cli/session.yaml', '.remotion/state.json']
        for relative, data in list(kept.items()) + [(p, b'local state') for p in omitted]:
            path = source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.assertEqual(self.run_install(), ['alpha', 'beta'])
        for relative, data in kept.items():
            self.assertEqual((self.destination / 'alpha' / relative).read_bytes(), data)
        for relative in omitted:
            self.assertFalse((self.destination / 'alpha' / relative).exists(), relative)
        self.assertTrue((self.destination / 'beta/SKILL.md').is_file())
        self.assertTrue((source / 'SkillToTable.exe').is_file())

    def test_single_skill_does_not_install_siblings(self):
        self.assertEqual(self.run_install('beta'), ['beta'])
        self.assertFalse((self.destination / 'alpha').exists())

    def test_existing_later_target_prevents_all_writes(self):
        target = self.destination / 'beta'
        target.mkdir(parents=True)
        (target / 'keep.txt').write_text('original', encoding='utf-8')
        with self.assertRaises(FileExistsError):
            self.run_install()
        self.assertFalse((self.destination / 'alpha').exists())
        self.assertEqual((target / 'keep.txt').read_text(), 'original')

    def test_copy_failure_does_not_expose_partial_skills(self):
        with patch.object(install.shutil, 'copy2', side_effect=OSError('simulated copy failure')):
            with self.assertRaises(OSError):
                self.run_install()
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_dry_run_creates_nothing(self):
        self.run_install(dry_run=True)
        self.assertFalse(self.destination.exists())

    def test_unknown_skill_creates_nothing(self):
        with self.assertRaises(ValueError):
            self.run_install('../outside')
        self.assertFalse(self.destination.exists())

    def test_old_suite_name_blocks_installation_without_deleting_old_skill(self):
        legacy = self.destination / 'skillto-int-rewrite'
        legacy.mkdir(parents=True)
        original = legacy / 'SKILL.md'
        original.write_text('Existing customized skill', encoding='utf-8')
        with self.assertRaisesRegex(FileExistsError, 'Legacy skill exists'):
            install.install(self.destination)
        self.assertEqual(original.read_text(encoding='utf-8'), 'Existing customized skill')
        self.assertEqual(list(self.destination.iterdir()), [legacy])

    def test_destination_inside_source_is_rejected(self):
        with self.assertRaises(ValueError):
            install.install(self.repo / 'skills/alpha/nested', repo_root=self.repo)
        self.assertFalse((self.repo / 'skills/alpha/nested').exists())

    def test_mismatched_skill_name_is_rejected(self):
        (self.repo / 'skills/alpha/SKILL.md').write_text('---\nname: other\ndescription: Test.\n---\n')
        with self.assertRaises(ValueError):
            self.run_install()
        self.assertFalse(self.destination.exists())

    def test_agent_defaults_are_independent(self):
        with patch.object(Path, 'home', return_value=self.root), patch.dict(os.environ, {'CODEX_HOME': str(self.root / 'custom-codex')}, clear=True):
            self.assertEqual(install.default_destination('codex'), self.root / '.agents/skills')
            self.assertEqual(install.default_destination('codex', codex_legacy=True), self.root / 'custom-codex/skills')
            self.assertEqual(install.default_destination('claude'), self.root / '.claude/skills')
        with patch.object(Path, 'home', return_value=self.root), patch.dict(os.environ, {}, clear=True):
            self.assertEqual(install.default_destination('codex'), self.root / '.agents/skills')
            self.assertEqual(install.default_destination('codex', codex_legacy=True), self.root / '.codex/skills')
            self.assertEqual(install.default_destination('claude'), self.root / '.claude/skills')
        with patch.dict(os.environ, {'CLAUDE_CONFIG_DIR': str(self.root / 'custom-claude')}):
            self.assertEqual(install.default_destination('claude'), self.root / 'custom-claude/skills')

    def test_cli_lists_skills_without_creating_destination(self):
        result = subprocess.run([sys.executable, str(install.REPO_ROOT / 'scripts/install.py'),
                                 '--list', '--destination', str(self.destination)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), list(install.discover_skills()))
        self.assertFalse(self.destination.exists())

    def test_cli_explicit_destination_overrides_legacy_default(self):
        result = subprocess.run([sys.executable, str(install.REPO_ROOT / 'scripts/install.py'),
                                 '--codex-legacy', '--skill', 'skillto-ai-studio-character-card',
                                 '--destination', str(self.destination)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.destination / 'skillto-ai-studio-character-card/SKILL.md').is_file())

    def test_cli_rejects_claude_legacy_flag_without_writes(self):
        result = subprocess.run([sys.executable, str(install.REPO_ROOT / 'scripts/install.py'),
                                 '--agent', 'claude', '--codex-legacy',
                                 '--destination', str(self.destination)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.destination.exists())

    def test_real_suite_has_complete_resources_after_install(self):
        available = install.discover_skills()
        installed = install.install(self.destination)
        self.assertEqual(set(installed), set(available))
        self.assertIn('skillto-ai-studio-rewrite', installed)
        self.assertTrue((self.destination / 'skillto-ai-studio/references/compatibility.md').is_file())
        for name, source in available.items():
            for relative in install.package_files(source):
                self.assertEqual((source / relative).read_bytes(),
                                 (self.destination / name / relative).read_bytes())
        self.assertFalse(any(p.name == '__pycache__' or p.suffix == '.exe'
                             for p in self.destination.rglob('*')))


if __name__ == '__main__':
    unittest.main()
