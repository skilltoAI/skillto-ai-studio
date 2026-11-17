import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from migration import snapshot
from shortlinks import ShortLinks, server_root


class RoutingTests(unittest.TestCase):
    def test_url_resolution_and_foreign_urls(self):
        self.assertEqual(server_root('http://192.168.3.55:8091/STASS/t/Ab123?x=1'), 'http://192.168.3.55:8091/STASS/')
        self.assertEqual(server_root('http://[::1]:8080/STASS/mcp'), 'http://[::1]:8080/STASS/')
        for url in ('http://host/?x=STASS', 'http://user:pass@host/STASS/', 'http://host/OTHER/STASS', 'http://host/STASSanything'):
            with self.assertRaises(ValueError): server_root(url)

    def test_persistent_immutable_deleted_and_collision(self):
        with tempfile.TemporaryDirectory() as temp:
            links = ShortLinks(temp)
            code = links.create('t', 'uuid1')
            self.assertEqual(len(code), 10)
            self.assertEqual(ShortLinks(temp).create('t', 'uuid1'), code)
            with self.assertRaises(KeyError): links.resolve('w', code)
            with patch('shortlinks.secrets.choice', side_effect=list(code)+list('0123456789')):
                self.assertEqual(links.create('t', 'uuid2'), '0123456789')
            view = links.create('s', 'snapshot', {'filter': ['x']})
            self.assertEqual(links.resolve('s', view)['view'], {'filter': ['x']})
            with self.assertRaises(ValueError): links.create('s', 'snapshot', {'filter': ['y']})
            links.delete('t', 'uuid1')
            with self.assertRaises(KeyError): links.resolve('t', code)
            with self.assertRaises(KeyError): links.create('t', 'uuid1')


class MigrationTests(unittest.TestCase):
    def test_copy_resume_and_sqlite_wal(self):
        with tempfile.TemporaryDirectory() as temp:
            src=Path(temp)/'source';src.mkdir();dest=Path(temp)/'target'
            (src/'sample.mp4').write_bytes(b'unchanged-media')
            con=sqlite3.connect(src/'library.sqlite3')
            try:
                con.execute('PRAGMA journal_mode=WAL');con.execute('CREATE TABLE items (id TEXT)');con.execute("INSERT INTO items VALUES ('stable')");con.commit()
                result=snapshot(src,dest)
                self.assertEqual(len(result['files']),2)
                copy=sqlite3.connect(dest/'library.sqlite3')
                try:self.assertEqual(copy.execute('SELECT id FROM items').fetchall(), [('stable',)])
                finally:copy.close()
                self.assertEqual((dest/'sample.mp4').read_bytes(), b'unchanged-media')
                self.assertEqual(len(snapshot(src,dest)['files']),2)
            finally:con.close()

    def test_overlap_and_nonempty_target_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            src=Path(temp)/'source';src.mkdir()
            with self.assertRaises(ValueError):snapshot(src,src/'nested')
            other=Path(temp)/'other';other.mkdir();(other/'unrelated').write_text('keep')
            with self.assertRaises(ValueError):snapshot(src,other)
            self.assertEqual((other/'unrelated').read_text(),'keep')


if __name__ == '__main__':unittest.main()
