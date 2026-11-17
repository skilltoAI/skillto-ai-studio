"""Version isolation, migration and atomic failures with temporary local tables."""
import copy
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch
from test_rewrite_analysis import AnalysisTests, store

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
spec = importlib.util.spec_from_file_location('motion_test_tables', Path(__file__).resolve().parents[1] / 'server.py')
tables = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tables)


class MotionStoryboardTests(AnalysisTests):
    def setUp(self):
        super().setUp()
        tables.ROOT = store.ROOT
        tables.CATALOG = store.ROOT / 'catalog.json'
        tables.TABLES = store.ROOT / 'tables'
        store.TABLE_STORE = tables
        kb = tables.table_workspace(dict(action='create', level='knowledge_base', name='KB'))
        project = tables.table_workspace(dict(action='create', level='project', knowledgeBaseId=kb['id'], name='Project'))
        self.table = tables.table_workspace(dict(action='create', level='table', knowledgeBaseId=kb['id'], projectId=project['id'], name='Board'))
        table = tables.load_table(self.table['id'])
        table.update(fields=[dict(name='custom', type='text', label='Unknown field')], tags=[dict(id='tag', name='Human')],
                     rows=[dict(id='r', fields={'custom': 'keep'}, media=[{'type': 'video', 'url': '/assets/a.mp4'}],
                                review={'score': 5}, tagIds=['tag'], history=[{'action': 'review'}])])
        tables.write_json(tables.table_path(table['id']), table)
        self.original = tables.table_path(table['id']).read_bytes()

    def change(self, action, revision=0, **extra):
        return store.dispatch(dict(action=action, id=self.item['id'], expectedRevision=revision, **extra))

    def test_link_clone_edit_switch_and_form_protection(self):
        before = copy.deepcopy(self.item)
        linked = self.change('link_motion_storyboard', tableId=self.table['id'])
        clone = self.change('create_motion_storyboard_version', 1)
        board = clone['motionStoryboard']
        self.assertEqual(board['activeVersionId'], 'v2')
        new_id = board['versions'][1]['tableId']
        self.assertNotEqual(new_id, self.table['id'])
        copied = tables.load_table(new_id)
        original = tables.load_table(self.table['id'])
        for key in ['fields', 'tags', 'rows']:
            self.assertEqual(copied[key], original[key])
        tables.table_save_row(dict(action='update', tableId=new_id, rowId='r', fields={'custom': 'new'}))
        self.assertEqual(tables.table_path(self.table['id']).read_bytes(), self.original)
        self.change('rename_motion_storyboard_version', 2, versionId='v2', label='独立新方案')
        self.change('select_motion_storyboard_version', 3, versionId='v1')
        saved = store.dispatch(dict(action='update', id=self.item['id'], manuscript=before))
        self.assertEqual(saved['motionStoryboard']['activeVersionId'], 'v1')
        self.assertEqual(saved['motionStoryboard']['versions'][1]['label'], '独立新方案')
        for key in ['openingStoryboard', 'fullStoryboard', 'transcriptVersions', 'sections', 'manuscriptAnalysis', 'keyframeAnalysis']:
            self.assertEqual(saved[key], before[key])
        self.assertEqual(linked['motionStoryboard']['versions'][0]['sourceTranscriptVersionId'], 'v0')

    def test_invalid_conflict_and_clone_failure_leave_no_orphans(self):
        self.change('link_motion_storyboard', tableId=self.table['id'])
        prior = store.FILE.read_bytes()
        catalog = tables.CATALOG.read_bytes()
        files = sorted(tables.TABLES.iterdir())
        for action, revision, kwargs in [
            ('create_motion_storyboard_version', 0, {}),
            ('create_motion_storyboard_version', True, {}),
            ('link_motion_storyboard', 1, {'tableId': '../bad'}),
            ('link_motion_storyboard', 1, {'tableId': self.table['id']}),
            ('select_motion_storyboard_version', 1, {'versionId': 'v9'}),
            ('rename_motion_storyboard_version', 1, {'versionId': 'v1', 'label': ''}),
        ]:
            with self.assertRaises(ValueError):
                self.change(action, revision, **kwargs)
            self.assertEqual(store.FILE.read_bytes(), prior)
        with patch.object(store, 'write', side_effect=OSError('Disk full')):
            with self.assertRaises(OSError):
                self.change('create_motion_storyboard_version', 1)
        self.assertEqual(store.FILE.read_bytes(), prior)
        self.assertEqual(tables.CATALOG.read_bytes(), catalog)
        self.assertEqual(sorted(tables.TABLES.iterdir()), files)

    def test_legacy_read_adds_empty_reference_only(self):
        data = store.read()
        data['manuscripts'][0].pop('motionStoryboard')
        store.write(data)
        before = store.FILE.read_bytes()
        current = store.read()['manuscripts'][0]
        self.assertEqual(current['motionStoryboard']['versions'], [])
        self.assertEqual(store.FILE.read_bytes(), before)
        self.assertEqual(current['openingStoryboard'], self.item['openingStoryboard'])
