"""Isolated analysis persistence tests; never touches the user's workspace."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parent / 'rewrite_system.py'
if not MODULE.exists():
    MODULE = Path(__file__).resolve().parents[1] / 'rewrite_system.py'
spec = importlib.util.spec_from_file_location('analysis_store', MODULE)
store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store)


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        store.ROOT = Path(self.temp.name)
        store.FILE = store.ROOT / 'rewrites.json'
        kb = store.dispatch({'action': 'create_kb', 'name': 'Isolated'})
        project = store.dispatch({'action': 'create_project', 'knowledgeBaseId': kb['id'], 'name': 'Analysis'})
        self.item = store.dispatch({'action': 'create', 'knowledgeBaseId': kb['id'], 'projectId': project['id'], 'manuscript': {
            'title': 'Test', 'transcript': '[00:00] source',
            'sections': {key: {'text': '', 'score': None, 'scoreNote': ''} for key in store.SECTION_KEYS},
            'similar': {key: [] for key in store.PLATFORMS}}})

    def tearDown(self):
        self.temp.cleanup()

    def save(self, key='manuscriptAnalysis', text='## Analysis', revision=0):
        return store.dispatch({'action': 'save_analysis', 'id': self.item['id'], 'analysisKey': key,
                               'text': text, 'expectedRevision': revision})

    def test_both_modules_history_idempotency_and_versions(self):
        versioned = store.dispatch({'action': 'create_version', 'id': self.item['id']})
        current = self.save()
        current = self.save('keyframeAnalysis', '| Fact | Evidence |\n| --- | --- |\n| A | B |')
        self.assertEqual(current['transcriptVersions'], versioned['transcriptVersions'])
        self.assertEqual(current['activeTranscriptVersionId'], 'v1')
        self.assertEqual(current['transcript'], self.item['transcript'])
        self.assertEqual(current['sections'], self.item['sections'])
        self.assertEqual(len(current['history']), 2)
        current = self.save(revision=1)
        self.assertEqual(len(current['history']), 2)
        self.assertEqual(store.read()['manuscripts'][0]['keyframeAnalysis']['revision'], 1)

    def test_stale_general_form_cannot_erase_new_analysis(self):
        self.save(text='new analysis')
        stale = dict(self.item)
        stale['title'] = 'Edited general form'
        current = store.dispatch({'action': 'update', 'id': self.item['id'], 'manuscript': stale})
        self.assertEqual(current['manuscriptAnalysis']['text'], 'new analysis')
        self.assertEqual(current['title'], 'Edited general form')

    def test_conflict_and_validation_are_atomic(self):
        self.save(text='first')
        before = store.FILE.read_bytes()
        for key, text, revision in [('manuscriptAnalysis', 'stale', 0), ('invalid', 'value', 1),
                                    ('manuscriptAnalysis', 'x'*100001, 1),
                                    ('manuscriptAnalysis', {}, 1), ('manuscriptAnalysis', 'bad revision', True)]:
            with self.assertRaises(store.RewriteError):
                self.save(key, text, revision)
            self.assertEqual(store.FILE.read_bytes(), before)

    def test_old_manuscript_gets_empty_modules_without_changing_v0(self):
        data = store.read()
        for key in store.ANALYSIS_KEYS:
            data['manuscripts'][0].pop(key)
        store.write(data)
        current = store.read()['manuscripts'][0]
        for key in store.ANALYSIS_KEYS:
            self.assertEqual(current[key], {'text': '', 'revision': 0, 'updatedAt': ''})
        self.assertEqual(current['transcriptVersions'][0]['text'], '[00:00] source')


if __name__ == '__main__':
    unittest.main()
