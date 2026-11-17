from __future__ import annotations

import csv
import asyncio
import io
import json
import sys
import tempfile
import threading
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from analysis import export_report, summarize
from auth import parse_cookies
from crawler import Capture, launch_options, manual_gate, visible_challenge, wait_for_human
from pacing import Pacer, TIERS, bind_checkpoint, retry_after_seconds
from dashboard import make_server, render
from db import connect, save_video, upsert_account
from keywords import expand
from parser import Account, account_from_mapping, count, load_accounts, parse_item, parse_profile, timestamp
from search import SearchCapture, ai_evidence, low_follower_hit, search_items
from detail import detail_item, video_target

TEST_ROOT = Path(__file__).resolve().parents[3] / ".test-tmp"
TEST_ROOT.mkdir(exist_ok=True)


def profile_payload(uid="123", sec="SEC123", handle="testcat"):
    return {"__DEFAULT_SCOPE__": {"webapp.user-detail": {"userInfo": {
        "user": {"id": uid, "secUid": sec, "uniqueId": handle, "nickname": "Test <cat>"},
        "stats": {"followerCount": 100, "videoCount": 4}}}}}


def raw_item(vid="1001", collect=1, share=1, **kwargs):
    raw = {"id": vid, "author": {"id": "123", "secUid": "SEC123", "uniqueId": "testcat"},
           "desc": "AI cat #aicat #cats", "createTime": 1792000000,
           "stats": {"diggCount": 10, "commentCount": 2, "shareCount": share, "playCount": "100000"},
           "video": {"cover": "https://example.com/cover.png", "duration": 10}}
    if collect is not None:
        raw["stats"]["collectCount"] = collect
    raw.update(kwargs)
    return raw


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.profile = parse_profile(profile_payload(), Account("testcat"))

    def test_cookie_formats_and_domain_scope(self):
        cases = ['Cookie: sessionid=demo=token; x=y',
                 '# Netscape HTTP Cookie File\n#HttpOnly_.tiktok.com\tTRUE\t/\tTRUE\t0\tsessionid\tdemo',
                 json.dumps({"cookies": [{"domain": ".tiktok.com", "name": "sessionid", "value": "demo"},
                                        {"domain": ".evil-tiktok.com", "name": "other", "value": "secret"}]})]
        for text in cases:
            cookies = parse_cookies(text)
            self.assertEqual(cookies[0]["name"], "sessionid")
            self.assertTrue(all(c["domain"] == ".tiktok.com" for c in cookies))

    def test_cookie_errors_do_not_echo_secrets(self):
        for text in ('sessionid=secret\ninjected=secret', 'x=MY_SECRET',
                     '[{"domain":"tiktok.com.evil.com","name":"sessionid","value":"MY_SECRET"}]',
                     '[{"domain":".tiktok.com","name":"sessionid","value":"MY_SECRET","expires":1}]'):
            with self.assertRaises(ValueError) as cm:
                parse_cookies(text)
            self.assertNotIn("MY_SECRET", str(cm.exception))

    def test_counts_and_dates(self):
        self.assertEqual(count("1.2M"), 1200000)
        self.assertEqual(count("2,345"), 2345)
        self.assertEqual(count(0), 0)
        for value in (None, "hidden", True, "-1", "NaN", "Infinity"):
            self.assertIsNone(count(value))
        self.assertEqual(timestamp(1792000000000), timestamp(1792000000))

    def test_account_url_restrictions(self):
        self.assertEqual(account_from_mapping("https://www.tiktok.com/@testcat").username, "testcat")
        for url in ('https://www.tiktok.com.evil.com/@cat', 'http://www.tiktok.com/@cat',
                    'https://www.tiktok.com/@cat/video/123', 'https://user:password@www.tiktok.com/@cat'):
            with self.assertRaises(ValueError):
                account_from_mapping(url)
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as temp:
            path = Path(temp) / "accounts.json"
            path.write_text('[{"username":"cat"},{"username":"CAT"}]')
            with self.assertRaises(ValueError):
                load_accounts(path)

    def test_profile_identity_pinning(self):
        self.assertIsNone(parse_profile(profile_payload(handle="other"), Account("testcat")))
        with self.assertRaises(ValueError):
            parse_profile(profile_payload(uid="456"), Account("testcat", user_id="123"))

    def test_author_requires_stable_match_and_rejects_conflicts(self):
        self.assertIsNotNone(parse_item(raw_item(), self.profile))
        for author in ({"uniqueId": "testcat"}, {"id": "456", "secUid": "SEC123"},
                       {"id": "123", "secUid": "OTHER"}):
            self.assertIsNone(parse_item(raw_item(author=author), self.profile))

    def test_missing_collect_and_topic_extraction(self):
        item = parse_item(raw_item(collect=None), self.profile)
        self.assertIsNone(item["collect_count"])
        self.assertEqual(item["topics"], ["aicat", "cats"])

    def test_bound_capture_and_pagination(self):
        capture = Capture(Account("testcat"))
        capture.pending.append(({"itemList": [raw_item()], "hasMore": False}, {"secUid": ["OTHER"]}))
        capture.hydration(profile_payload())
        self.assertFalse(capture.exhausted)
        self.assertEqual(capture.items, {})
        capture.pending.append(({"itemList": [raw_item()], "hasMore": False}, {"secUid": ["SEC123"]}))
        capture.drain()
        self.assertTrue(capture.exhausted)
        self.assertEqual(len(capture.items), 1)

    def test_empty_or_hydration_is_not_full_coverage(self):
        capture = Capture(Account("testcat"))
        capture.hydration({**profile_payload(), "ItemModule": {"1001": raw_item()}})
        self.assertFalse(capture.exhausted)
        self.assertEqual(len(capture.items), 1)

    def test_search_capture_dedup_and_evidence(self):
        payload = {"data": [{"item": raw_item()}, {"item": raw_item()}]}
        pool = {}
        SearchCapture("AI cat", pool).add(payload)
        SearchCapture("KI Katze", pool).add(payload)
        self.assertEqual(len(pool), 1)
        self.assertEqual(pool["1001"]["queries"], ["AI cat", "KI Katze"])
        self.assertEqual(ai_evidence(raw_item())[0], "creator_text")
        self.assertEqual(ai_evidence(raw_item(desc="real cat"))[0], "unverified")
        self.assertEqual(len(search_items(payload)), 2)

    def test_low_follower_nulls_and_thresholds(self):
        self.assertTrue(low_follower_hit(100000, 10000))
        self.assertFalse(low_follower_hit(99999, 100))
        self.assertFalse(low_follower_hit(10000000, 10001))
        self.assertIsNone(low_follower_hit(1000000, None))
        self.assertIsNone(low_follower_hit(1000000, 0))

    def test_video_target_and_detail_scope(self):
        self.assertEqual(video_target("https://www.tiktok.com/@testcat/video/1001")[1], "1001")
        for url in ("https://tiktok.com.evil/@cat/video/1", "http://www.tiktok.com/@cat/video/1"):
            with self.assertRaises(ValueError):
                video_target(url)
        raw = raw_item()
        self.assertEqual(detail_item({"__DEFAULT_SCOPE__": {"webapp.video-detail": {"itemInfo": {"itemStruct": raw}}}}), raw)

    def test_keyword_languages_and_ambiguity_notes(self):
        result = expand(["AI dog", "AI cat"], ["en", "ja", "de", "fr"])
        self.assertEqual({q["language"] for q in result["queries"]}, {"en", "ja", "de", "fr"})
        self.assertTrue(any(q["query"] == "KI Katze" for q in result["queries"]))
        self.assertTrue(any("toutou" in q["query"] for q in result["queries"]))
        self.assertTrue(result["notes"])


class PacingTests(unittest.TestCase):
    def test_six_stages_and_no_stop_after_six_then_recovery(self):
        pacer = Pacer(SimpleNamespace())
        with patch("pacing.random.uniform", side_effect=lambda low, high: (low + high) / 2) as draw:
            for index in range(8):
                low, high = TIERS[min(index, 5)]
                delay = pacer.observe(usable=False)
                draw.assert_called_with(low, high)
                self.assertTrue(low <= delay <= high)
                self.assertEqual(pacer.streak, index + 1)
                self.assertIsNone(pacer.stop_reason)
        self.assertEqual(pacer.slow_factor, 8)
        self.assertIsNone(pacer.stop_reason)
        for _ in range(3):
            pacer.observe(usable=True)
        self.assertEqual(pacer.slow_factor, 4)
        self.assertEqual(pacer.streak, 0)
        self.assertTrue(1 <= pacer.observe(usable=False) <= 5)

    def test_server_wait_is_respected_and_access_denial_needs_attention(self):
        pacer = Pacer(SimpleNamespace())
        self.assertEqual(pacer.observe(usable=False, exhausted=True), 8)
        self.assertEqual(pacer.streak, 0)
        with patch("pacing.random.uniform", return_value=1000):
            self.assertEqual(pacer.observe(error="rate_limited", retry_after=7200), 7200)
        self.assertIsNone(pacer.stop_reason)
        pacer.observe(error="access_denied")
        self.assertEqual(pacer.stop_reason, "access_denied")
        self.assertTrue(pacer.events[-1]["stopped"])
        response = SimpleNamespace(headers={"retry-after": "7200"})
        self.assertEqual(retry_after_seconds(response), 7200)

    def test_same_pending_unit_retries_seven_failures_then_succeeds(self):
        pacer = Pacer(SimpleNamespace())
        operation = AsyncMock(side_effect=[{"ok": False}] * 7 + [{"ok": True}])
        pacer.pause = AsyncMock()
        result = asyncio.run(pacer.run(operation, "query:AI cat", lambda r: {"usable": r["ok"]}))
        self.assertTrue(result["ok"])
        self.assertEqual(operation.await_count, 8)
        self.assertEqual(pacer.pause.await_count, 7)
        self.assertEqual([e["stage"] for e in pacer.events], [1, 2, 3, 4, 5, 6, 6])
        self.assertEqual({e["unit"] for e in pacer.events}, {"query:AI cat"})
        self.assertIsNone(pacer.pending_unit)

    def test_cancelled_wait_is_durable_and_resume_honors_remaining_deadline(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as temp:
            args = SimpleNamespace(checkpoint=Path(temp) / "state.json", resume=False)
            pacer, state = bind_checkpoint(args, {"query": "AI cat"})
            pacer.pending_unit = "query:AI cat"
            pacer.observe(usable=False)
            clock = datetime.now(timezone.utc)
            with patch("pacing.now", return_value=clock), patch("pacing.asyncio.sleep", AsyncMock(side_effect=asyncio.CancelledError)):
                with self.assertRaises(asyncio.CancelledError):
                    asyncio.run(pacer.pause(65))
            saved = json.loads(args.checkpoint.read_text(encoding="utf-8"))
            self.assertEqual(saved["pacing"]["status"], "waiting")
            args.resume = True
            del args._pacer
            restored, _ = bind_checkpoint(args, {"query": "AI cat"})
            self.assertEqual(restored.streak, 1)
            self.assertEqual(restored.pending_unit, "query:AI cat")
            output = io.StringIO()
            with patch("pacing.now", return_value=clock + timedelta(seconds=15)), patch("pacing.asyncio.sleep", AsyncMock()) as sleep, redirect_stdout(output):
                asyncio.run(restored.resume_wait())
            self.assertAlmostEqual(sum(c.args[0] for c in sleep.await_args_list), 50)
            self.assertTrue(all(c.args[0] <= 10 for c in sleep.await_args_list))
            self.assertIn("remaining_seconds", output.getvalue())
            self.assertIn("resuming", output.getvalue())
            self.assertIsNone(json.loads(args.checkpoint.read_text(encoding="utf-8"))["pacing"]["wake_at"])
            with self.assertRaises(ValueError):
                bind_checkpoint(args, {"query": "different"})

    def test_headless_default_and_manual_challenge_switch(self):
        from run import build_parser
        args = build_parser().parse_args(["search", "--keyword", "AI cat"])
        self.assertTrue(launch_options(args)["headless"])
        self.assertEqual(args.challenge_wait, 0)
        self.assertFalse(hasattr(args, "anomaly_limit"))
        page = SimpleNamespace()
        import asyncio
        with patch("crawler.page_gate", AsyncMock(return_value="challenge_required")), patch("crawler.visible_challenge", AsyncMock(return_value=None)) as visible:
            self.assertIsNone(asyncio.run(manual_gate(page, args)))
            visible.assert_awaited_once()
            args.no_manual_challenge = True
            self.assertEqual(asyncio.run(manual_gate(page, args)), "challenge_required")
            self.assertEqual(visible.await_count, 1)

    def test_visible_challenge_returns_cookies_and_rechecks(self):
        import asyncio
        args = SimpleNamespace(headed=False, browser_executable=None, browser_channel="msedge", timeout=10, wait_ms=1, challenge_wait=4)
        manual_page = SimpleNamespace(goto=AsyncMock(return_value=None), wait_for_timeout=AsyncMock(), is_closed=lambda: False)
        manual_context = SimpleNamespace(new_page=AsyncMock(return_value=manual_page), cookies=AsyncMock(return_value=[{"name": "fixture", "value": "private"}]))
        browser = SimpleNamespace(new_context=AsyncMock(return_value=manual_context), close=AsyncMock())
        launch = AsyncMock(return_value=browser)
        original_context = SimpleNamespace(browser=SimpleNamespace(browser_type=SimpleNamespace(launch=launch)), storage_state=AsyncMock(return_value={"cookies": []}), add_cookies=AsyncMock())
        page = SimpleNamespace(context=original_context, url="https://www.tiktok.com/search?q=cat", reload=AsyncMock(return_value=None), wait_for_timeout=AsyncMock())
        with patch("crawler.page_gate", AsyncMock(return_value=None)):
            self.assertIsNone(asyncio.run(visible_challenge(page, args)))
        self.assertFalse(launch.call_args.kwargs["headless"])
        original_context.add_cookies.assert_awaited_once()
        page.reload.assert_awaited_once()
        browser.close.assert_awaited_once()

    def test_human_window_waits_beyond_old_timeout_and_emits_status(self):
        args = SimpleNamespace(challenge_wait=0)
        page = SimpleNamespace(is_closed=lambda: False, wait_for_timeout=AsyncMock())
        # 902 seconds elapsed, beyond the old 900-second default, then solved.
        gates = ["challenge_required"] * 451 + [None]
        output = io.StringIO()
        with patch("crawler.page_gate", AsyncMock(side_effect=gates)), redirect_stdout(output):
            self.assertIsNone(asyncio.run(wait_for_human(page, args)))
        self.assertEqual(page.wait_for_timeout.await_count, 451)
        self.assertIn('"waited_seconds": 900', output.getvalue())
        self.assertEqual(args._pacer.status, "running")

    def test_permanent_target_failure_does_not_retry(self):
        pacer = Pacer(SimpleNamespace())
        operation = AsyncMock(return_value={"error": "identity_mismatch"})
        pacer.pause = AsyncMock()
        asyncio.run(pacer.run(operation, "account:cat", lambda r: r))
        operation.assert_awaited_once()
        pacer.pause.assert_not_awaited()


@contextmanager
def fake_playwright():
    """Run the real workflow schedulers with a local fake browser factory."""
    context = SimpleNamespace(add_cookies=AsyncMock(), close=AsyncMock())
    browser = SimpleNamespace(new_context=AsyncMock(return_value=context), close=AsyncMock())
    pw = SimpleNamespace(chromium=SimpleNamespace(launch=AsyncMock(return_value=browser)))

    class Manager:
        async def __aenter__(self):
            return pw

        async def __aexit__(self, *exc):
            pass

    module = ModuleType("playwright.async_api")
    module.async_playwright = Manager
    with patch.dict(sys.modules, {"playwright": ModuleType("playwright"), "playwright.async_api": module}):
        yield browser


class WorkflowRetryTests(unittest.TestCase):
    def test_search_and_author_retries_and_resume_do_not_skip_failed_units(self):
        from run import build_parser
        from search import search
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as temp:
            root = Path(temp)
            queries = root / "queries.json"
            queries.write_text('["AI cat"]', encoding="utf-8")
            args = build_parser().parse_args(["search", "--keyword", "AI cat", "--queries", str(queries),
                "--min-videos", "1", "--db", str(root / "data.sqlite3"), "--report", str(root / "report.json"),
                "--checkpoint", str(root / "checkpoint.json")])
            conn = connect(args.db)
            attempts = 0

            async def query(context, query, pool, args, state):
                nonlocal attempts
                attempts += 1
                healthy = attempts == 8
                if healthy:
                    pool["1001"] = {"raw": raw_item(createTime=int(datetime.now(timezone.utc).timestamp()) - 100),
                                    "queries": ["AI cat"], "captured_at": datetime.now(timezone.utc).isoformat()}
                return {**query, "error_type": None if healthy else "navigation_failed", "coverage": "sampled" if healthy else "no_data",
                        "usable_items": int(healthy), "endpoint_exhausted": healthy}

            verified = parse_profile(profile_payload(), Account("testcat"))
            try:
                with fake_playwright(), patch("search.search_query", AsyncMock(side_effect=query)) as queries_mock, \
                     patch("search.verify_author", AsyncMock(side_effect=[None, None, verified])) as authors, \
                     patch.object(Pacer, "pause", AsyncMock()), redirect_stdout(io.StringIO()):
                    self.assertEqual(asyncio.run(search(args, [], conn)), 0)
                    self.assertEqual(queries_mock.await_count, 8)
                    self.assertEqual(authors.await_count, 3)
                    checkpoint = json.loads(args.checkpoint.read_text(encoding="utf-8"))
                    self.assertEqual(len(checkpoint["query_runs"]), 8)
                    self.assertEqual([e["stage"] for e in checkpoint["pacing"]["events"]], [1, 2, 3, 4, 5, 6, 6, 1, 2])
                    self.assertEqual(len(json.loads(args.report.read_text(encoding="utf-8"))["videos"]), 1)
                    args.resume = True
                    del args._pacer
                    self.assertEqual(asyncio.run(search(args, [], conn)), 0)
                    self.assertEqual((queries_mock.await_count, authors.await_count), (8, 3))
            finally:
                conn.close()

    def test_account_and_video_entry_points_retry_and_checkpoint_final_results(self):
        from run import build_parser
        from crawler import crawl
        from detail import collect_videos
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as temp:
            root = Path(temp)
            conn = connect(root / "data.sqlite3")
            try:
                for command in ("crawl", "video"):
                    target = ["--account", "@testcat"] if command == "crawl" else ["--url", "https://www.tiktok.com/@testcat/video/1001"]
                    args = build_parser().parse_args([command, *target, "--db", str(root / "data.sqlite3"),
                        "--checkpoint", str(root / f"{command}.json"), "--report", str(root / "report.json")])
                    if command == "crawl":
                        failed = dict(username="testcat", status="failed", coverage="unknown", error_type="no_verifiable_items", videos_seen=0, saved_count=0)
                        success = dict(username="testcat", status="ok", coverage="complete", error_type=None, videos_seen=1, saved_count=1)
                        patch_target = "crawler.crawl_account"
                    else:
                        failed = dict(video_id="1001", error_type="author_unverified", row=None, retry_after=0)
                        success = dict(video_id="1001", error_type=None, row={"video_id": "1001"}, retry_after=0)
                        patch_target = "detail.capture_video"
                    with fake_playwright(), patch(patch_target, AsyncMock(side_effect=[failed] * 3 + [success])) as operation, \
                         patch.object(Pacer, "pause", AsyncMock()), redirect_stdout(io.StringIO()):
                        if command == "crawl":
                            results = asyncio.run(crawl([Account("testcat")], [], args, conn))
                            self.assertEqual(results, [success])
                        else:
                            self.assertEqual(asyncio.run(collect_videos(args, [], conn)), 0)
                        self.assertEqual(operation.await_count, 4)
                        checkpoint = json.loads(args.checkpoint.read_text(encoding="utf-8"))
                        self.assertEqual(len(checkpoint["results"]), 1)
                        self.assertIsNone(checkpoint["pacing"]["pending_unit"])
            finally:
                conn.close()


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=TEST_ROOT)
        self.path = Path(self.temp.name) / "test.sqlite3"
        self.conn = connect(self.path)
        self.profile = parse_profile(profile_payload(), Account("testcat"))
        upsert_account(self.conn, self.profile)

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def test_snapshots_idempotence_and_latest_metrics(self):
        for day, views in (("2026-10-21T10:00:00+00:00", 10), ("2026-10-21T11:00:00+00:00", 20), ("2026-10-22T10:00:00+00:00", 30)):
            item = parse_item(raw_item(), self.profile)
            item["view_count"] = views
            save_video(self.conn, self.profile, item, day)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0], 2)
        report = summarize(self.conn, now=datetime(2026, 10, 22, 12, tzinfo=timezone.utc))
        self.assertEqual(report["videos"][0]["view_count"], 30)

    def test_null_averages_strict_high_rule_and_publish_window(self):
        for vid, collect, share in (("1001", 0, 0), ("1002", 0, 0), ("1003", 30, 0), ("1004", None, 50)):
            save_video(self.conn, self.profile, parse_item(raw_item(vid, collect, share), self.profile))
        old = parse_item(raw_item("9999", 9999, 9999, createTime=1700000000), self.profile)
        save_video(self.conn, self.profile, old)
        report = summarize(self.conn, now=datetime(2026, 10, 22, 12, tzinfo=timezone.utc))
        self.assertEqual(len(report["videos"]), 4)
        self.assertEqual(report["accounts"][0]["means"]["collect_count"], 10)
        self.assertEqual(report["accounts"][0]["sample_counts"]["collect_count"], 3)
        self.assertEqual({v["video_id"] for v in report["videos"] if v["high_interaction"]}, {"1003", "1004"})

    def test_db_rejects_wrong_author(self):
        item = parse_item(raw_item(), self.profile)
        item["author_user_id"] = "456"
        with self.assertRaises(ValueError):
            save_video(self.conn, self.profile, item)

    def test_export_csv_formula_and_json_null(self):
        item = parse_item(raw_item(collect=None, desc="=HYPERLINK(1)"), self.profile)
        save_video(self.conn, self.profile, item)
        report = summarize(self.conn, now=datetime(2026, 10, 22, 12, tzinfo=timezone.utc))
        csv_path, jsonl = Path(self.temp.name) / "v.csv", Path(self.temp.name) / "v.jsonl"
        export_report(report, csv_path=csv_path, jsonl=jsonl)
        with csv_path.open(encoding="utf-8-sig") as f:
            self.assertTrue(next(csv.DictReader(f))["title"].startswith("'="))
        self.assertIsNone(json.loads(jsonl.read_text())["collect_count"])

    def test_dashboard_http_and_escaping(self):
        save_video(self.conn, self.profile, parse_item(raw_item(desc="<script>alert(1)</script>"), self.profile))
        self.conn.commit()
        report = summarize(self.conn, now=datetime(2026, 10, 22, 12, tzinfo=timezone.utc))
        self.assertNotIn("<script>", render(report))
        server = make_server(self.path, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}"
            self.assertEqual(urlopen(url).status, 200)
            self.assertEqual(json.load(urlopen(url + "/api/report"))["days"], 30)
            with self.assertRaises(HTTPError) as cm:
                urlopen(Request(url, headers={"Host": "evil.example"}))
            self.assertEqual(cm.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
