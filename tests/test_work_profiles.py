"""Integration of the source installer with the preferences read by both UIs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import install
import work_profiles as profiles


class WorkProfilesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        config = patch.dict(os.environ, {'STASS_PREFERENCES_DIR':str(self.root / 'prefs'),
                                         'CLAUDE_CONFIG_DIR': str(self.root / 'claude'),
                                         'PYTHONIOENCODING':'utf-8'})
        config.start()
        self.addCleanup(config.stop)

    def run_cli(self, agent, *args, answer=None, success=True):
        cmd = [sys.executable, '-B', '-X', 'utf8', str(ROOT / 'scripts/install.py'),
               '--destination', str(self.root / agent), '--agent', agent, *args]
        result = subprocess.run(cmd, input=answer, encoding='utf-8', capture_output=True)
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return result.stdout + result.stderr

    def test_catalog_coverage_and_dependency_closure(self):
        distributed = set(install.discover_skills()) - {profiles.PARENT}
        self.assertEqual(distributed, {profiles.PARENT + '-' + k for k,r in profiles.ITEMS.items() if not r.get('kind')})
        for item in profiles.ITEMS.values():
            self.assertGreater(len(item['description']), 95)
            profiles.checked(item['optional'] + item['defaults'], profiles.GROUPS)
        items = profiles.resolve(['generate'], ['h3-workflow'])
        self.assertEqual(set(items), {'h3-workflow','depth-gray-replica','workflow-mcp','character-card'})

    def test_first_question_and_subsequent_augmentation(self):
        out = self.run_cli('codex', '--groups', answer='5\n')
        self.assertEqual(out.count('你日常需要处理哪些工作'), 1)
        self.assertEqual(profiles.profile()['groups'], ['teach'])
        initial = self.root / 'codex' / (profiles.PARENT + '-rewrite') / 'SKILL.md'
        stamp = initial.stat().st_mtime_ns
        self.run_cli('codex', '--augment', '--groups', 'AI视频剪辑')
        self.assertEqual(stamp, initial.stat().st_mtime_ns)
        self.assertEqual(profiles.profile()['groups'], ['teach','edit'])
        info = profiles.snapshot('codex')
        self.assertEqual(info['status']['rewrite'], '已安装')
        self.assertEqual(info['status']['h3-workflow'], '待安装')
        initial.write_text('local edition', encoding='utf-8')
        self.assertIn('差异', profiles.snapshot('codex')['status']['rewrite'])
        self.run_cli('codex', '--groups', '5', success=False)
        self.assertEqual(initial.read_text(encoding='utf-8'), 'local edition')

    def test_multiple_hosts_dry_run_exact_selection_and_stale_save(self):
        self.run_cli('claude', '--groups', '2、5', '--dry-run')
        self.assertFalse((self.root / 'prefs').exists())
        self.run_cli('claude', '--groups', '2、5')
        self.assertEqual(set(profiles.profile()['groups']), {'social','teach'})
        self.assertEqual(profiles.snapshot('claude')['status']['rewrite'], '已安装')
        self.assertEqual(profiles.snapshot('workbody')['status']['rewrite'], '宿主待验证')
        self.run_cli('codex', '--groups', 'generate', '--items', 'h3-workflow')
        current = profiles.profile()
        with self.assertRaises(ValueError):
            profiles.save([], [], current['revision'] - 1)
        profiles.save([], [], current['revision'])
        self.assertEqual(profiles.snapshot('codex')['status']['h3-workflow'], '已安装')
        self.assertEqual(profiles.dispatch({'action':'navigation'})['views'], [])
