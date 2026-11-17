"""Observe the regular TikTok profile page. No request signing or challenge bypass."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from auth import is_tiktok_host
from db import save_video, upsert_account
from parser import Account, item_candidates, parse_item, parse_profile, utc_now
from pacing import bind_checkpoint, pacer_for, retry_after_seconds, scroll_pause

POST_PATH = "/api/post/item_list/"
PROFILE_PATH = "/api/user/detail/"
ERRORS = {"identity_mismatch", "login_required", "access_denied", "rate_limited", "challenge_required",
          "private_account", "navigation_failed", "profile_unverified", "no_verifiable_items", "payload_error"}


class BrowserGate(Exception):
    """A browser gate; the scheduler distinguishes timed limits from human attention."""


class Capture:
    def __init__(self, account: Account):
        self.account = account
        self.profile = None
        self.items: dict[str, dict] = {}
        self.pending: list[tuple[dict, dict]] = []
        self.post_responses = 0
        self.exhausted = False
        self.error = None
        self.empty_responses = 0
        self.retry_after = 0

    def accept_profile(self, payload: dict):
        try:
            profile = parse_profile(payload, self.account)
            if profile:
                if self.profile and (profile["user_id"], profile["sec_uid"]) != (self.profile["user_id"], self.profile["sec_uid"]):
                    self.error = "identity_mismatch"
                else:
                    self.profile = profile
        except ValueError:
            self.error = "identity_mismatch"

    def hydration(self, payload: dict):
        if not isinstance(payload, dict):
            return
        self.accept_profile(payload)
        if self.profile:
            # Initial SIGI_STATE posts may be partial; this never proves pagination exhaustion.
            for raw in item_candidates(payload):
                if (item := parse_item(raw, self.profile)):
                    self.items[item["video_id"]] = item
        self.drain()

    def drain(self):
        if not self.profile:
            return
        pending, self.pending = self.pending, []
        for payload, query in pending:
            if query.get("secUid") != [self.profile["sec_uid"]]:
                continue
            status = payload.get("statusCode", payload.get("status_code", 0))
            if str(status) != "0":
                self.error = "payload_error"
                continue
            if not any(isinstance(payload.get(k), list) for k in ("itemList", "item_list")):
                continue
            self.post_responses += 1
            for raw in item_candidates(payload):
                if (item := parse_item(raw, self.profile)):
                    self.items[item["video_id"]] = item
            more = payload.get("hasMore", payload.get("has_more"))
            # Only an explicit end-of-list signal from a bound post response proves exhaustion.
            if more is False or more == 0 or more == "0":
                self.exhausted = True

    async def response(self, response):
        parsed = urlparse(response.url)
        if not is_tiktok_host((parsed.hostname or "").lower()) or parsed.path not in {POST_PATH, PROFILE_PATH}:
            return
        query = parse_qs(parsed.query)
        if parsed.path == PROFILE_PATH:
            handles = query.get("uniqueId", query.get("unique_id", []))
            if handles and [v.casefold() for v in handles] != [self.account.username.casefold()]:
                return
        elif self.profile and query.get("secUid") != [self.profile["sec_uid"]]:
            return
        if response.status in (401, 403, 429):
            self.error = {401: "login_required", 403: "access_denied", 429: "rate_limited"}[response.status]
            self.retry_after = max(self.retry_after, retry_after_seconds(response))
            return
        if not response.ok:
            self.error = "payload_error"
            return
        try:
            payload = await response.json()
            if not isinstance(payload, dict):
                return
            if parsed.path == PROFILE_PATH:
                self.accept_profile(payload)
            else:
                self.pending.append((payload, query))
            self.drain()
        except Exception:
            # Browser exceptions and response bodies may contain session-bearing URLs.
            self.empty_responses += 1


async def page_gate(page) -> str | None:
    path = urlparse(page.url).path.lower()
    if path.startswith("/login"):
        return "login_required"
    if any(p in path for p in ("/captcha", "/verify", "/challenge")):
        return "challenge_required"
    for selector in ('iframe[src*="captcha"]', '[id*="captcha-verify"]', '[data-e2e="captcha"]'):
        locator = page.locator(selector)
        for i in range(await locator.count()):
            if await locator.nth(i).is_visible():
                return "challenge_required"
    if await page.get_by_text("This account is private", exact=False).count():
        return "private_account"
    return None


MANUAL_GATES = {"challenge_required", "login_required"}


async def wait_for_human(page, args):
    limit = getattr(args, "challenge_wait", 0)
    elapsed = 0
    pacer = pacer_for(args)
    while not limit or elapsed < limit:
        if page.is_closed():
            return "manual_window_closed"
        gate = await page_gate(page)
        if gate not in MANUAL_GATES:
            pacer.status = "running"
            pacer.state.pop("human_verification", None)
            pacer.persist()
            return gate
        if elapsed % 30 == 0:
            pacer.status = "waiting_for_human"
            pacer.persist()
            print(json.dumps({"attention": "请在已打开的浏览器中完成 TikTok 验证/登录；任务保留进度，完成后继续。",
                              "unit": pacer.pending_unit, "reason": gate,
                              "waited_seconds": elapsed, "timeout_seconds": limit or None}, ensure_ascii=False), flush=True)
        await page.wait_for_timeout(2000)
        elapsed += 2
    return gate


async def manual_gate(page, args, initial_gate=None) -> str | None:
    gate = await page_gate(page) or initial_gate
    if gate in MANUAL_GATES and not getattr(args, "no_manual_challenge", False):
        pacer = pacer_for(args)
        pacer.status = "waiting_for_human"
        pacer.state["human_verification"] = {"reason": gate, "unit": pacer.pending_unit}
        pacer.persist()
        print(json.dumps({"attention": "发现 TikTok 验证/登录要求，正在显示浏览器，请人工处理；完成后继续原任务。",
                          "reason": gate, "unit": pacer.pending_unit}, ensure_ascii=False), flush=True)
    if gate in MANUAL_GATES and not args.headed and not getattr(args, "no_manual_challenge", False):
        return await visible_challenge(page, args)
    if gate in MANUAL_GATES and args.headed and not getattr(args, "no_manual_challenge", False):
        return await wait_for_human(page, args)
    return gate


async def visible_challenge(page, args):
    """Transfer the authorized session in memory to a visible manual verification window."""
    browser = None
    try:
        options = launch_options(args)
        options["headless"] = False
        browser = await page.context.browser.browser_type.launch(**options)
        context = await browser.new_context(storage_state=await page.context.storage_state(),
                                            viewport={"width": 1440, "height": 1000}, locale="en-US")
        manual_page = await context.new_page()
        response = await manual_page.goto(page.url, wait_until="domcontentloaded", timeout=args.timeout * 1000)
        if response and response.status in (403, 429):
            # A rendered CAPTCHA can use HTTP 403: allow the human-visible gate first.
            if await page_gate(manual_page) not in MANUAL_GATES:
                return {403: "access_denied", 429: "rate_limited"}[response.status]
        await manual_page.wait_for_timeout(args.wait_ms)
        gate = await wait_for_human(manual_page, args)
        if gate:
            return gate
        await page.context.add_cookies(await context.cookies())
        response = await page.reload(wait_until="domcontentloaded", timeout=args.timeout * 1000)
        await scroll_pause(page, args)
        gate = await page_gate(page)
        if gate:
            return gate
        if response and response.status in (401, 403, 429):
            return {401: "login_required", 403: "access_denied", 429: "rate_limited"}[response.status]
        return None
    except Exception:
        return "challenge_required"
    finally:
        if browser:
            await browser.close()


async def hydration(page, capture: Capture):
    for selector in ("#__UNIVERSAL_DATA_FOR_REHYDRATION__", "#SIGI_STATE"):
        locator = page.locator(selector)
        if await locator.count():
            try:
                capture.hydration(json.loads(await locator.first.text_content() or "{}"))
            except (ValueError, TypeError, KeyError):
                continue


def launch_options(args) -> dict:
    options = {"headless": not args.headed}
    if args.browser_executable:
        options["executable_path"] = args.browser_executable
    elif args.browser_channel:
        options["channel"] = args.browser_channel
    return options


async def crawl_account(browser, cookies, account, args, conn, run_id) -> dict:
    started = utc_now()
    # Pin previously verified identities so a recycled handle cannot change ownership.
    stored = conn.execute("SELECT user_id,sec_uid FROM accounts WHERE lower(username)=lower(?)", (account.username,)).fetchone()
    if stored:
        if (account.user_id and account.user_id != stored[0]) or (account.sec_uid and account.sec_uid != stored[1]):
            capture = Capture(account)
            capture.error = "identity_mismatch"
        else:
            account = Account(account.username, account.name, stored[0], stored[1])
            capture = Capture(account)
    else:
        capture = Capture(account)
    context = None
    tasks: set[asyncio.Task] = set()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=args.days)).isoformat(timespec="seconds")
    until = utc_now()
    try:
        if capture.error:
            raise ValueError("identity_mismatch")
        context = await browser.new_context(viewport={"width": 1440, "height": 1000}, locale="en-US")
        await context.add_cookies(cookies)
        page = await context.new_page()

        def on_response(response):
            task = asyncio.create_task(capture.response(response))
            tasks.add(task)
            task.add_done_callback(tasks.discard)

        page.on("response", on_response)
        for attempt in range(1):
            response = await page.goto(account.url, wait_until="domcontentloaded", timeout=args.timeout * 1000)
            if response and response.status in (401, 403, 429):
                capture.error = {401: "login_required", 403: "access_denied", 429: "rate_limited"}[response.status]
                capture.retry_after = max(capture.retry_after, retry_after_seconds(response))
            await page.wait_for_timeout(args.wait_ms * (attempt + 1))
            capture.error = await manual_gate(page, args, capture.error)
            await hydration(page, capture)
            if capture.error:
                break
            await page.mouse.move(1050, 700)
            idle = 0
            for _ in range(args.max_scrolls):
                if capture.error or capture.exhausted:
                    break
                previous = len(capture.items)
                await page.mouse.wheel(0, 850)
                await scroll_pause(page, args)
                capture.error = await manual_gate(page, args, capture.error)
                idle = idle + 1 if len(capture.items) == previous else 0
                if idle >= 3:
                    break
            if capture.items or capture.exhausted or capture.error:
                break
        if tasks:
            await asyncio.gather(*list(tasks), return_exceptions=True)
    except Exception:
        capture.error = capture.error or "navigation_failed"
    finally:
        if tasks:
            for task in list(tasks):
                task.cancel()
            await asyncio.gather(*list(tasks), return_exceptions=True)
        if context:
            cookies[:] = await context.cookies()
            await context.close()
    error = capture.error
    if not capture.profile:
        error = error or "profile_unverified"
    elif not capture.items and not capture.exhausted:
        error = error or "no_verifiable_items"
    coverage = "complete" if capture.exhausted and not error else "partial" if capture.items else "unknown"
    status = "failed" if error else "ok" if coverage == "complete" else "partial"
    saved = 0
    if capture.profile and error != "identity_mismatch":
        with conn:
            upsert_account(conn, capture.profile)
            for item in capture.items.values():
                if cutoff <= item["published_at"] <= until:
                    save_video(conn, capture.profile, item)
                    saved += 1
            conn.execute("UPDATE accounts SET last_crawled_at=?,last_status=?,last_coverage=? WHERE user_id=?",
                         (utc_now(), status, coverage, capture.profile["user_id"]))
    with conn:
        conn.execute("""INSERT INTO account_runs
          (run_id,username,account_id,started_at,finished_at,status,coverage,error_type,videos_seen,saved_count)
          VALUES (?,?,?,?,?,?,?,?,?,?)""", (run_id, account.username,
                       capture.profile["user_id"] if capture.profile else None, started, utc_now(),
                       status, coverage, error, len(capture.items), saved))
    return dict(username=account.username, status=status, coverage=coverage, error_type=error,
                videos_seen=len(capture.items), saved_count=saved, retry_after=capture.retry_after)


async def crawl(accounts, cookies, args, conn) -> list[dict]:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise ValueError("Playwright is required for crawling. Install scripts/requirements.txt and run doctor.") from None
    with conn:
        run_id = conn.execute("INSERT INTO crawl_runs(started_at,status,account_count,days) VALUES (?,?,?,?)",
                              (utc_now(), "running", len(accounts), args.days)).lastrowid
    results = []
    pacer, checkpoint = bind_checkpoint(args, {"accounts": [dict(username=a.username, user_id=a.user_id, sec_uid=a.sec_uid) for a in accounts],
                                             "days": args.days, "db": str(args.db.resolve())})
    await pacer.resume_wait()
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(**launch_options(args))
            try:
                for index, account in enumerate(accounts):
                    unit = "account:" + account.username
                    if unit in checkpoint["results"]:
                        results.append(checkpoint["results"][unit])
                        continue
                    result = await pacer.run(lambda: crawl_account(browser, cookies, account, args, conn, run_id), unit,
                        lambda r: dict(error=r["error_type"], usable=bool(r["videos_seen"]),
                                       exhausted=r["coverage"] == "complete", retry_after=r.get("retry_after", 0)))
                    results.append(result)
                    print(json.dumps(result), flush=True)
                    if pacer.stop_reason:
                        break
                    checkpoint["results"][unit] = result
                    pacer.persist()
                    if index + 1 < len(accounts):
                        await pacer.pause(pacer.interval * pacer.slow_factor)
            finally:
                await browser.close()
    except Exception:
        with conn:
            conn.execute("UPDATE crawl_runs SET finished_at=?,status='failed',error_count=? WHERE id=?",
                         (utc_now(), len(accounts), run_id))
        raise ValueError("Browser/crawl failed; run doctor with the same browser options. Raw exception hidden.") from None
    errors = sum(r["status"] == "failed" for r in results)
    partial = any(r["status"] == "partial" for r in results)
    status = "failed" if errors == len(results) else "partial" if errors or partial else "ok"
    with conn:
        conn.execute("UPDATE crawl_runs SET finished_at=?,status=?,success_count=?,item_count=?,error_count=? WHERE id=?",
                     (utc_now(), status, sum(r["status"] == "ok" for r in results),
                      sum(r["saved_count"] for r in results), errors, run_id))
    return results


async def doctor(args):
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(**launch_options(args))
            page = await browser.new_page()
            await page.goto("about:blank")
            print(json.dumps({"browser_launch": "ok", "version": browser.version, "live_login_verified": False}))
            await browser.close()
    except Exception:
        raise ValueError("Browser launch failed. Install Playwright and Chromium, or pass --browser-channel msedge/chrome. Raw exception hidden.") from None
