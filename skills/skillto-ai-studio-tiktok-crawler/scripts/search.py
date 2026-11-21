"""Browser-rendered search sampling with checkpoints and explicit coverage limits."""
from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from auth import is_tiktok_host
from crawler import BrowserGate, Capture, hydration, launch_options, manual_gate
from db import save_video, upsert_account
from keywords import expand
from parser import Account, count, first, item_candidates, parse_item, timestamp, utc_now
from pacing import pacer_for, retry_after_seconds, scroll_pause

SEARCH_PATHS = {"/api/search/general/full/", "/api/search/item/full/", "/api/search/general/"}


def search_items(payload):
    if not isinstance(payload, dict):
        return []
    result = item_candidates(payload)
    for row in payload.get("data", []) if isinstance(payload.get("data"), list) else []:
        if isinstance(row, dict):
            item = row.get("item") or row.get("itemStruct")
            if isinstance(item, dict):
                result.append(item)
    scope = payload.get("__DEFAULT_SCOPE__", {})
    detail = scope.get("webapp.search-detail")
    if isinstance(detail, dict):
        result.extend(search_items(detail))
    return result


def ai_evidence(raw):
    text = str(raw.get("desc") or "")
    flags = [key for key in ("isAigc", "isAI", "aigcLabelType") if raw.get(key)]
    if re.search(r"(?i)ai[- ]generated", str(raw.get("AIGCDescription") or "")):
        flags.append("AIGCDescription")
    terms = re.findall(r"(?i)(?:\bai\b|#aigenerated\w*|#aicat\w*|#aidog\w*|\bki\b|\bia\b|AI生成|AI再現|AIリメイク|#aivideo\w*|#aipets\w*)", text)
    if flags:
        return "platform_label", ",".join(flags)
    if terms:
        return "creator_text", ",".join(dict.fromkeys(t.lower() for t in terms))
    return "unverified", "Keyword match alone does not establish AI generation/remake."


def production_hint(raw):
    text = str(raw.get("desc") or "")
    if re.search(r"(?i)\b(tutorial|how to|step.by.step)\b|作り方|やり方|教程|教学|教えて", text):
        return "tutorial"
    if re.search(r"(?i)motion transfer|remake|recreat|AI再現|AIリメイク|復刻|复刻", text):
        return "remake_claim"
    return "ai_claim" if ai_evidence(raw)[0] != "unverified" else "unverified"


def low_follower_hit(views, followers, max_followers=10000, min_views=100000, min_ratio=10):
    if views is None or followers is None:
        return None
    if followers <= 0:
        return None
    return followers <= max_followers and views >= min_views and views / followers >= min_ratio


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


class SearchCapture:
    def __init__(self, query, pool):
        self.query = query
        self.pool = pool
        self.error = None
        self.responses = 0
        self.empty_responses = 0
        self.exhausted = False
        self.application_codes = []
        self.usable_items = 0
        self.retry_after = 0

    def add(self, payload):
        for raw in search_items(payload):
            vid = str(raw.get("id") or "")
            author = raw.get("author")
            if not vid.isdigit() or not isinstance(author, dict) or not str(author.get("id") or "").isdigit() or not author.get("secUid"):
                continue
            self.usable_items += 1
            # Only selected public fields are checkpointed; no raw headers, request URLs or session state.
            safe = {k: raw[k] for k in ("id", "desc", "createTime", "create_time", "stats", "statsV2", "video", "textExtra", "isAigc", "isAI", "aigcLabelType", "AIGCDescription", "authorStats", "authorStatsV2") if k in raw}
            safe["author"] = {k: author.get(k) for k in ("id", "secUid", "uniqueId", "nickname")}
            existing = self.pool.get(vid)
            hits = existing["queries"] if existing else []
            if self.query not in hits:
                hits.append(self.query)
            self.pool[vid] = {"raw": safe, "queries": hits, "captured_at": utc_now()}

    async def response(self, response):
        parsed = urlparse(response.url)
        if not is_tiktok_host((parsed.hostname or "").lower()) or parsed.path not in SEARCH_PATHS:
            return
        query = parse_qs(parsed.query)
        keyword = query.get("keyword", query.get("q", []))
        if keyword and keyword != [self.query]:
            return
        if response.status in (401, 403, 429):
            self.error = {401: "login_required", 403: "access_denied", 429: "rate_limited"}[response.status]
            self.retry_after = max(self.retry_after, retry_after_seconds(response))
            return
        try:
            payload = await response.json()
            if not isinstance(payload, dict):
                return
            status = payload.get("status_code", payload.get("statusCode", 0))
            # Some web responses carry a nonzero application code alongside the same
            # publicly rendered cards. Retain only those already returned cards, flag
            # the application code; HTTP gates have their own handling.
            if str(status) != "0":
                self.application_codes.append(status)
                if not search_items(payload):
                    self.error = "payload_error"
                    return
            self.responses += 1
            self.add(payload)
            more = payload.get("has_more", payload.get("hasMore"))
            if more is False or more == 0 or more == "0":
                self.exhausted = True
        except Exception:
            self.empty_responses += 1


async def search_query(context, query, pool, args, checkpoint_state=None):
    page = await context.new_page()
    capture = SearchCapture(query["query"], pool)
    tasks = set()
    before = len(pool)

    def on_response(response):
        task = asyncio.create_task(capture.response(response))
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    page.on("response", on_response)
    try:
        response = await page.goto("https://www.tiktok.com/search?q=" + quote(query["query"]),
                                   wait_until="domcontentloaded", timeout=args.timeout * 1000)
        if response and response.status in (401, 403, 429):
            capture.error = {401: "login_required", 403: "access_denied", 429: "rate_limited"}[response.status]
            capture.retry_after = max(capture.retry_after, retry_after_seconds(response))
        await page.wait_for_timeout(args.wait_ms)
        capture.error = await manual_gate(page, args, capture.error)
        if not capture.error:
            await page.mouse.move(1050, 700)
            for selector in ("#__UNIVERSAL_DATA_FOR_REHYDRATION__", "#SIGI_STATE"):
                loc = page.locator(selector)
                if await loc.count():
                    try:
                        capture.add(json.loads(await loc.first.text_content() or "{}"))
                    except (ValueError, TypeError):
                        pass
            idle = 0
            for _ in range(args.max_scrolls):
                if capture.error or capture.exhausted:
                    break
                previous = len(pool)
                await page.mouse.wheel(0, 850)
                await scroll_pause(page, args)
                capture.error = await manual_gate(page, args, capture.error)
                if len(pool) != previous:
                    if checkpoint_state is not None:
                        atomic_json(args.checkpoint, checkpoint_state)
                    print(json.dumps({"query_progress": query["query"], "unique_total": len(pool), "target": args.min_videos}), flush=True)
                if len(pool) >= args.min_videos and not getattr(args, "all_queries", False):
                    break
                idle = idle + 1 if len(pool) == previous else 0
                if idle >= 4:
                    break
        if tasks:
            await asyncio.gather(*list(tasks), return_exceptions=True)
        # Leave the page visible for manual login/diagnostics when the query returned no usable data.
        if len(pool) == before and args.headed and args.interactive_wait and capture.error not in {"access_denied", "rate_limited"}:
            await page.screenshot(path=str(args.checkpoint.parent / "last-search.png"))
            print(json.dumps({"attention": "No search data. Browser is open for manual login/verification.",
                              "query": query["query"], "wait_seconds": args.interactive_wait}), flush=True)
            for _ in range(args.interactive_wait // 2):
                await page.wait_for_timeout(2000)
                if len(pool) > before or capture.error:
                    break
        await page.screenshot(path=str(args.checkpoint.parent / "last-search.png"))
    except Exception:
        capture.error = capture.error or "navigation_failed"
    finally:
        if tasks:
            for task in list(tasks):
                task.cancel()
            await asyncio.gather(*list(tasks), return_exceptions=True)
        await page.close()
    return {**query, "captured_at": utc_now(), "new_unique": len(pool) - before, "responses": capture.responses,
            "empty_responses": capture.empty_responses, "error_type": capture.error,
            "usable_items": capture.usable_items,
            "retry_after": capture.retry_after,
            "application_codes": list(dict.fromkeys(capture.application_codes)),
            "endpoint_exhausted": capture.exhausted,
            "coverage": "sampled" if len(pool) > before else "no_data"}


async def verify_author(context, raw_author, args):
    username = str(raw_author.get("uniqueId") or "")
    if not re.fullmatch(r"[\w.]{1,24}", username, flags=re.ASCII):
        raise BrowserGate("invalid_target")
    account = Account(username, user_id=str(raw_author["id"]), sec_uid=raw_author["secUid"])
    capture = Capture(account)
    page = await context.new_page()
    try:
        response = await page.goto(account.url, wait_until="domcontentloaded", timeout=args.timeout * 1000)
        initial = {401: "login_required", 403: "access_denied", 429: "rate_limited"}.get(response.status) if response else None
        if initial == "rate_limited":
            exc = BrowserGate(initial)
            exc.retry_after = retry_after_seconds(response)
            raise exc
        await page.wait_for_timeout(args.wait_ms)
        gate = await manual_gate(page, args, initial)
        if gate:
            raise BrowserGate(gate)
        await hydration(page, capture)
        if capture.error == "identity_mismatch":
            raise BrowserGate("identity_mismatch")
        return capture.profile if not capture.error else None
    except BrowserGate:
        raise
    except Exception:
        return None
    finally:
        await page.close()


async def search(args, cookies, conn):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise ValueError("Playwright required for TikTok search; install scripts/requirements.txt.") from None
    expansion = expand(args.keyword, args.languages.split(","))
    if args.queries:
        loaded = json.loads(args.queries.read_text(encoding="utf-8-sig"))
        queries = loaded.get("queries", []) if isinstance(loaded, dict) else loaded
        queries = [dict(query=q, language="custom") if isinstance(q, str) else q for q in queries]
    else:
        # Round robin languages/animals before adding variants.
        buckets = {}
        for query in expansion["queries"]:
            buckets.setdefault((query["language"], query["animal"]), []).append(query)
        queries = [values[i] for i in range(max(map(len, buckets.values()), default=0)) for values in buckets.values() if i < len(values)]
    if args.max_queries:
        queries = queries[:args.max_queries]
    state = {"pool": {}, "query_runs": [], "author_profiles": {}, "started_at": utc_now()}
    if args.resume and args.checkpoint.is_file():
        state = json.loads(args.checkpoint.read_text(encoding="utf-8"))
    args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
    signature = {"queries": queries, "days": args.days, "min_videos": args.min_videos, "all_queries": args.all_queries,
                 "db": str(args.db.resolve())}
    if state.get("signature", signature) != signature:
        raise ValueError("Checkpoint targets/options differ; choose a separate --checkpoint.")
    state["signature"] = signature
    # A sample containing usable cards can still have failed; do not skip it on resume.
    completed = {q["query"] for q in state["query_runs"] if not q.get("error_type")
                 and (q.get("usable_items") or q.get("endpoint_exhausted"))}
    pool = state["pool"]
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(**launch_options(args))
        context = await browser.new_context(viewport={"width": 1440, "height": 1000}, locale="en-US")
        await context.add_cookies(cookies)
        try:
            pacer = pacer_for(args)
            pacer.bind(state, lambda: atomic_json(args.checkpoint, state))
            await pacer.resume_wait()
            for query in queries:
                if query["query"] in completed:
                    continue
                if len(pool) >= args.min_videos and not args.all_queries:
                    break
                async def attempt_query():
                    result = await search_query(context, query, pool, args, state)
                    state["query_runs"].append(result)
                    atomic_json(args.checkpoint, state)
                    print(json.dumps({**result, "unique_total": len(pool), "target": args.min_videos}), flush=True)
                    return result
                await pacer.run(attempt_query, "query:" + query["query"],
                    lambda r: dict(error=r["error_type"], usable=bool(r["usable_items"]),
                                   exhausted=r["endpoint_exhausted"], retry_after=r.get("retry_after", 0)))
                if pacer.stop_reason:
                    break
                if len(pool) >= args.min_videos and not args.all_queries:
                    break
                await pacer.pause(pacer.interval * pacer.slow_factor)
            cutoff = (datetime.now(timezone.utc) - timedelta(days=args.days)).isoformat(timespec="seconds")
            until = utc_now()
            candidates = [record for record in pool.values() if cutoff <= (timestamp(first(record["raw"], "createTime", "create_time")) or "") <= until]
            candidates.sort(key=lambda r: count(first(r["raw"], "statsV2.playCount", "stats.playCount")) or -1, reverse=True)
            verification_candidates = candidates
            if args.verify_top:
                selected_ids = {r["raw"]["id"] for r in candidates[:args.verify_top]}
                for record in candidates:
                    raw = record["raw"]
                    if low_follower_hit(count(first(raw, "statsV2.playCount", "stats.playCount")),
                                        count(first(raw, "authorStatsV2.followerCount", "authorStats.followerCount")),
                                        args.max_followers, args.min_views, args.min_ratio):
                        selected_ids.add(raw["id"])
                verification_candidates = [r for r in candidates if r["raw"]["id"] in selected_ids]
            # Do not spend additional profile requests on content that cannot enter
            # this AI-content ranking. Explicit source-video review remains separate.
            verification_candidates = [r for r in verification_candidates
                                       if ai_evidence(r["raw"])[0] != "unverified"
                                       and production_hint(r["raw"]) != "tutorial"]
            # Verify authors for all recent candidates, bounded by a user-visible limit.
            for record in verification_candidates:
                if pacer.stop_reason:
                    break
                author = record["raw"]["author"]
                uid = str(author["id"])
                if state["author_profiles"].get(uid) or uid in state.get("unavailable_authors", {}):
                    continue
                if sum(bool(v) for v in state["author_profiles"].values()) >= args.max_authors:
                    break
                async def attempt_author():
                    try:
                        profile = await verify_author(context, author, args)
                        return {"profile": profile, "error": None}
                    except BrowserGate as exc:
                        return {"profile": None, "error": str(exc), "retry_after": getattr(exc, "retry_after", 0)}
                verified = await pacer.run(attempt_author, "author:" + str(author.get("uniqueId")),
                    lambda r: dict(error=r["error"], usable=bool(r["profile"]), retry_after=r.get("retry_after", 0)))
                if pacer.stop_reason:
                    state["verification_gate"] = pacer.stop_reason
                    pacer.persist()
                    break
                if verified["profile"]:
                    state["author_profiles"][uid] = verified["profile"]
                    state.pop("verification_gate", None)
                else:
                    state.setdefault("unavailable_authors", {})[uid] = verified["error"]
                pacer.persist()
                print(json.dumps({"author_checked": author.get("uniqueId"), "verified": bool(verified["profile"])}), flush=True)
                await pacer.pause(pacer.interval * pacer.slow_factor)
        finally:
            await context.close()
            await browser.close()
    rows = []
    for record in candidates:
        raw = record["raw"]
        profile = state["author_profiles"].get(str(raw["author"]["id"]))
        if not profile or not (item := parse_item(raw, profile)):
            continue
        with conn:
            upsert_account(conn, profile)
            save_video(conn, profile, item, record["captured_at"])
            conn.execute("UPDATE accounts SET last_crawled_at=?,last_status='partial',last_coverage='search_sample' WHERE user_id=?",
                         (utc_now(), profile["user_id"]))
        evidence, detail = ai_evidence(raw)
        followers = profile["follower_count"]
        hit = low_follower_hit(item["view_count"], followers, args.max_followers, args.min_views, args.min_ratio)
        rows.append({**item, "username": profile["username"], "follower_count": followers,
                     "captured_at": record["captured_at"], "queries": record["queries"],
                     "ai_evidence": evidence, "ai_evidence_detail": detail,
                     "production_hint": production_hint(raw),
                     "views_per_follower": item["view_count"] / followers if followers and item["view_count"] is not None else None,
                     "low_follower_viral": hit, "verification": "author_profile_verified"})
    # AI evidence is a declared/labelled signal, not visual or forensic verification.
    ranked = sorted([r for r in rows if r["view_count"] is not None and r["ai_evidence"] != "unverified" and r["production_hint"] != "tutorial"], key=lambda r: r["view_count"], reverse=True)
    report = dict(generated_at=utc_now(), started_at=state["started_at"], days=args.days, cutoff=cutoff,
                  min_videos=args.min_videos, searched_unique=len(pool), sample_target_met=len(pool) >= args.min_videos,
                  recent_candidates=len(candidates), author_verified_videos=len(rows),
                  verification_candidate_count=len(verification_candidates), verification_top_limit=args.verify_top,
                  verification_gate=state.get("verification_gate"),
                  pacing=pacer.snapshot(),
                  coverage="search_sample", query_runs=state["query_runs"], expansion=expansion,
                  thresholds=dict(max_followers=args.max_followers, min_views=args.min_views, min_views_per_follower=args.min_ratio),
                  videos=rows, top_videos=ranked[:args.top], low_follower_viral=[r for r in ranked if r["low_follower_viral"] is True],
                  limitations=["Ranked by observed views within this captured sample; not a platform-wide ranking.",
                               "AI label/creator text requires content review; keyword match alone is excluded from ranked lists.",
                               "Followers are measured now, not at publication. Missing followers cannot qualify as low-follower viral.",
                               "Publication window is UTC rolling days; query language does not prove creator region or video language."])
    atomic_json(args.report, report)
    print(json.dumps({"searched_unique": len(pool), "sample_target_met": report["sample_target_met"], "recent_candidates": len(candidates),
                      "verified": len(rows), "ranked": len(ranked), "low_follower_viral": len(report["low_follower_viral"])}), flush=True)
    return 0 if report["sample_target_met"] and not pacer.stop_reason else 3
