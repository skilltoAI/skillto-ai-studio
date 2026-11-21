from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import report_system as reports


class ReportRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "catalog.json").write_text(json.dumps({"knowledgeBases": [{
            "id": "kb", "name": "Knowledge", "projects": [
                {"id": "project", "name": "One", "tables": []},
                {"id": "other", "name": "Two", "tables": []}]}]}), encoding="utf-8")
        self.env = patch.dict(os.environ, {"SKILLTO_TABLE_ROOT": str(self.root)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_failed_metabase_create_does_not_leave_registry(self):
        with patch.object(reports, "mb_request", side_effect=reports.ReportError("Metabase down", 503)):
            with self.assertRaises(reports.ReportError):
                reports.create_report({"name": "Demo", "knowledgeBaseId": "kb", "projectId": "project"})
        self.assertFalse((self.root / "reports" / "catalog.json").exists())

    def test_crud_keeps_stable_id_and_history(self):
        calls = []
        def fake(method, path, payload=None):
            calls.append((method, path, payload))
            return {"id": 12, "name": payload.get("name")} if method == "POST" else {"id": 12}
        with patch.object(reports, "mb_request", side_effect=fake):
            created = reports.create_report({"name": "Demo", "knowledgeBaseId": "kb", "projectId": "project"})
            updated = reports.update_report({"reportId": created["id"], "name": "Revised",
                                             "knowledgeBaseId": "kb", "projectId": "other"})
            archived = reports.archive_report({"reportId": created["id"]})
            restored = reports.archive_report({"reportId": created["id"]}, True)
        self.assertEqual(created["id"], updated["id"])
        self.assertEqual(restored["id"], created["id"])
        self.assertEqual(updated["projectId"], "other")
        self.assertEqual(archived["status"], "archived")
        self.assertEqual(restored["status"], "active")
        self.assertEqual(len(reports._read_registry()["history"]), 4)
        self.assertIn(("PUT", "/api/dashboard/12", {"archived": True}), calls)


class CollectedDataTests(unittest.TestCase):
    def test_frozen_roster_and_snapshots(self):
        root = Path(os.environ.get("STASS_REPORT_TEST_DATA_ROOT", os.environ.get("SKILLTO_TABLE_ROOT", str(Path.home() / "skillto-table-data"))))
        raw = root / "reports" / "raw" / "2026-11-07"
        if not raw.exists():
            self.skipTest("local collection is not present")
        frozen = json.loads((raw / "roster.json").read_text(encoding="utf-8"))["accounts"]
        profiles = json.loads((raw / "profiles.json").read_text(encoding="utf-8"))
        posts = json.loads((raw / "videos.json").read_text(encoding="utf-8"))
        self.assertEqual(len(frozen), 74)
        self.assertEqual(sum(a["group"] == "AI付费流教学号" for a in frozen), 10)
        self.assertEqual(len({a["secUid"] for a in frozen}), 74)
        self.assertEqual(len(profiles), 74)
        self.assertTrue(all(p["capturedAt"].startswith("2026-11-07") for p in profiles))
        self.assertTrue(all(p["followerCount"] is not None and p["totalFavorited"] is not None for p in profiles))
        self.assertEqual(len(posts), 74)
        self.assertTrue(all(p["complete"] for p in posts))
        ids = [video["id"] for account in posts for video in account["videos"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_month_boundary_null_metrics_and_coverage(self):
        database = os.environ.get('STASS_REPORT_TEST_DATABASE', '')
        if not database.startswith('stass_test_'):
            self.skipTest('an isolated stass_test_ database is required')
        try:
            import psycopg
        except ImportError:
            self.skipTest('psycopg is not installed')
        try:
            config_file = Path(os.environ.get("SKILLTO_REPORT_CONFIG", str(
                Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SkillToTable" / "reporting" / "config.json")))
            settings = json.loads(config_file.read_text(encoding="utf-8"))
            db = psycopg.connect(host="127.0.0.1", port=5434, dbname=database,
                                 user="report_admin", password=settings["dbPassword"])
        except (OSError, KeyError, psycopg.OperationalError):
            self.skipTest("local reporting database is unavailable")
        identifier = str(uuid.uuid4())
        try:
            with db.cursor() as cur:
                cur.execute("INSERT INTO account_roster VALUES (%s,'验收测试','边界账号',%s,NULL,'test',now())",
                            (identifier, identifier))
                cur.execute("INSERT INTO account_month_coverage VALUES (%s,'2026-09-01','partial','分页缺失',1,now()),(%s,'2026-10-01','complete',NULL,2,now())",
                            (identifier, identifier))
                cur.execute("""INSERT INTO video_observations
                    VALUES (%s,%s,'2026-09-30 15:59:59+00',now(),'九月',NULL,3,NULL,'test'),
                           (%s,%s,'2026-09-30 16:00:00+00',now(),'十月',NULL,NULL,4,'test')""",
                            (identifier + '-sep', identifier, identifier + '-oct', identifier))
                cur.execute("""INSERT INTO video_observations
                    VALUES (%s,%s,'2026-09-30 15:59:59+00',now(),'重复',NULL,9,9,'test')
                    ON CONFLICT (video_id) DO NOTHING""", (identifier + '-sep', identifier))
                cur.execute("""SELECT month::text,coverage_status,video_count,like_count,collect_count
                    FROM account_month_metrics WHERE account_row_id=%s ORDER BY month""", (identifier,))
                rows = cur.fetchall()
            self.assertEqual(rows, [('2026-09-01', 'partial', 1, 3, None),
                                    ('2026-10-01', 'complete', 1, None, 4)])
        finally:
            db.rollback()
            db.close()


if __name__ == "__main__":
    unittest.main()
