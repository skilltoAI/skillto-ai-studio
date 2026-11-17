"""Offline browser capture integration: all TikTok requests are fulfilled locally."""
from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from crawler import crawl_account
from db import connect
from parser import Account, utc_now
from search import search_query
from test_crawler import TEST_ROOT, profile_payload, raw_item


async def main(channel):
    from playwright.async_api import async_playwright
    with tempfile.TemporaryDirectory(dir=TEST_ROOT) as temp:
        root = Path(temp)
        conn = connect(root / "browser.sqlite3")
        run_id = conn.execute("INSERT INTO crawl_runs(started_at,status,account_count,days) VALUES (?,?,?,?)", (utc_now(), "running", 1, 30)).lastrowid
        conn.commit()
        raw = raw_item(createTime=int(datetime.now(timezone.utc).timestamp()) - 100)
        foreign = raw_item("9999", author={"id": "456", "secUid": "OTHER"}, createTime=raw["createTime"])
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(channel=channel, headless=True)

            async def route(handler):
                path = handler.request.url
                if "/api/post/item_list/" in path:
                    await handler.fulfill(json={"statusCode": 0, "itemList": [raw, foreign], "hasMore": False})
                elif "/api/search/general/full/" in path:
                    await handler.fulfill(json={"status_code": 403, "data": [{"item": raw}, {"item": raw}], "has_more": 0})
                else:
                    payload = json.dumps(profile_payload())
                    script = "fetch('/api/search/general/full/?keyword=AI%20cat')" if "/search?" in path else "fetch('/api/post/item_list/?secUid=SEC123')"
                    await handler.fulfill(content_type="text/html", body=f'<html><body><script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">{payload}</script><script>{script}</script><p>Public fixture</p></body></html>')

            await browser.new_context()  # Routing is installed on each account context below.
            original_new_context = browser.new_context

            async def routed_context(**kwargs):
                context = await original_new_context(**kwargs)
                await context.route("**/*", route)
                return context

            browser.new_context = routed_context
            args = SimpleNamespace(days=30, timeout=10, wait_ms=100, max_scrolls=1, headed=False,
                                   challenge_wait=0, interactive_wait=0, checkpoint=root / "checkpoint.json", min_videos=1000)
            result = await crawl_account(browser, [{"name": "sessionid", "value": "offline-fixture", "domain": ".tiktok.com", "path": "/"}], Account("testcat"), args, conn, run_id)
            assert result["status"] == "ok", result
            assert result["saved_count"] == 1, result
            assert conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0] == 1
            context = await routed_context()
            pool = {}
            search_result = await search_query(context, {"query": "AI cat", "language": "en"}, pool, args)
            assert len(pool) == 1, search_result
            assert search_result["application_codes"] == [403], search_result
            assert search_result["error_type"] is None, search_result
            await context.close()
            await browser.close()
        conn.close()
    print("Offline browser integration passed: profile identity, owned-item filtering, complete pagination, search deduplication and nonzero application-code diagnostics.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser-channel", default="msedge")
    asyncio.run(main(parser.parse_args().browser_channel))
