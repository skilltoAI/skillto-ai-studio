"""Capture explicit source pages with author verification and durable retries."""
from __future__ import annotations

import asyncio
import json
import re
from urllib.parse import parse_qs, urlparse

from auth import is_tiktok_host
from crawler import BrowserGate, launch_options, manual_gate
from db import save_video, upsert_account
from parser import parse_item, utc_now
from search import ai_evidence, atomic_json, low_follower_hit, production_hint, verify_author
from pacing import bind_checkpoint, retry_after_seconds


def video_target(url):
    parsed = urlparse(url)
    match = re.fullmatch(r"/@([\w.]{1,24})/video/(\d+)/?", parsed.path, flags=re.ASCII)
    if parsed.scheme != "https" or parsed.netloc.lower() not in {"tiktok.com", "www.tiktok.com"} or not match:
        raise ValueError("Use a canonical HTTPS TikTok /@username/video/id URL.")
    return match[1], match[2], f"https://www.tiktok.com/@{match[1]}/video/{match[2]}"


def detail_item(payload):
    if not isinstance(payload, dict):
        return None
    detail = payload.get("__DEFAULT_SCOPE__", {}).get("webapp.video-detail", payload)
    raw = detail.get("itemInfo", {}).get("itemStruct")
    return raw if isinstance(raw, dict) else None


async def capture_video(context, target, args, conn, profiles):
    username, vid, url = target
    page = await context.new_page()
    found, tasks = [], set()
    error, retry_after, row = None, 0, None

    async def on_response(response):
        nonlocal error, retry_after
        parsed = urlparse(response.url)
        if not is_tiktok_host(parsed.hostname or "") or parsed.path != "/api/item/detail/" or parse_qs(parsed.query).get("itemId") != [vid]:
            return
        if response.status in (401, 403, 429):
            error = {401: "login_required", 403: "access_denied", 429: "rate_limited"}[response.status]
            retry_after = max(retry_after, retry_after_seconds(response))
            return
        try:
            raw = detail_item(await response.json())
            if raw:
                found.append(raw)
        except Exception:
            pass

    def listener(response):
        task = asyncio.create_task(on_response(response))
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    page.on("response", listener)
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=args.timeout * 1000)
        if response and response.status in (401, 403, 429):
            error = {401: "login_required", 403: "access_denied", 429: "rate_limited"}[response.status]
            retry_after = max(retry_after, retry_after_seconds(response))
        await page.wait_for_timeout(args.wait_ms)
        error = await manual_gate(page, args, error)
        if not error:
            locator = page.locator("#__UNIVERSAL_DATA_FOR_REHYDRATION__")
            if await locator.count():
                raw = detail_item(json.loads(await locator.first.text_content() or "{}"))
                if raw:
                    found.append(raw)
            if tasks:
                await asyncio.gather(*list(tasks), return_exceptions=True)
            raw = next((r for r in found if str(r.get("id")) == vid), None)
            author = raw.get("author") if raw else None
            if not isinstance(author, dict) or not author.get("id") or not author.get("secUid"):
                error = "item_unverified"
            elif str(author.get("uniqueId", "")).casefold() != username.casefold():
                error = "identity_mismatch"
            else:
                uid = str(author["id"])
                if not profiles.get(uid):
                    profiles[uid] = await verify_author(context, author, args)
                profile = profiles[uid]
                item = parse_item(raw, profile) if profile else None
                if not item:
                    error = "author_unverified"
                else:
                    captured_at = utc_now()
                    with conn:
                        upsert_account(conn, profile)
                        save_video(conn, profile, item, captured_at)
                    evidence, detail = ai_evidence(raw)
                    followers = profile["follower_count"]
                    row = {**item, "username": profile["username"], "follower_count": followers,
                           "captured_at": captured_at, "queries": ["explicit_source_video"],
                           "ai_evidence": evidence, "ai_evidence_detail": detail,
                           "production_hint": production_hint(raw), "verification": "video_page_and_author_profile_verified",
                           "views_per_follower": item["view_count"] / followers if followers and item["view_count"] is not None else None,
                           "low_follower_viral": low_follower_hit(item["view_count"], followers)}
    except BrowserGate as exc:
        error = str(exc)
        retry_after = max(retry_after, getattr(exc, "retry_after", 0))
    except Exception:
        error = error or "navigation_failed"
    finally:
        for task in list(tasks):
            task.cancel()
        if tasks:
            await asyncio.gather(*list(tasks), return_exceptions=True)
        await page.close()
    return dict(video_id=vid, username=username, error_type=error, retry_after=retry_after, row=row, captured_at=utc_now())


async def collect_videos(args, cookies, conn):
    targets = [video_target(url) for url in args.url]
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise ValueError("Playwright required for video capture.") from None
    pacer, checkpoint = bind_checkpoint(args, {"urls": [t[2] for t in targets], "db": str(args.db.resolve())})
    await pacer.resume_wait()
    profiles = {}
    blocked = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(**launch_options(args))
        context = await browser.new_context(viewport={"width": 1440, "height": 1000}, locale="en-US")
        await context.add_cookies(cookies)
        try:
            for index, target in enumerate(targets):
                unit = "video:" + target[1]
                if unit in checkpoint["results"]:
                    continue
                result = await pacer.run(lambda: capture_video(context, target, args, conn, profiles), unit,
                    lambda r: dict(error=r["error_type"], usable=bool(r["row"]), retry_after=r["retry_after"]))
                print(json.dumps({"video_id": target[1], "status": result["error_type"] or "ok"}), flush=True)
                if pacer.stop_reason:
                    blocked.append(result)
                    break
                checkpoint["results"][unit] = result
                pacer.persist()
                if index + 1 < len(targets):
                    await pacer.pause(pacer.interval * pacer.slow_factor)
        finally:
            await context.close()
            await browser.close()
    results = list(checkpoint["results"].values()) + blocked
    rows = [r["row"] for r in results if r.get("row")]
    failures = [{k: v for k, v in r.items() if k != "row"} for r in results if r["error_type"]]
    atomic_json(args.report, {"generated_at": utc_now(), "videos": rows, "failures": failures,
                              "coverage": "explicit_source_pages", "requested": len(targets),
                              "pacing": pacer.snapshot()})
    return 2 if failures else 0
