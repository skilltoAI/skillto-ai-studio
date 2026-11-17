"""Freeze tagged account roster and collect 2026-11-07 profile/video observations."""
from __future__ import annotations

import concurrent.futures
import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener
from zoneinfo import ZoneInfo

TABLE_ID = "56fa8754-8d40-4225-8541-0be4729ade73"
GROUPS = ("AI付费流教学号", "AI自然流教学号")
START = "2026-09-01"
END = "2026-11-01"
TZ = ZoneInfo("Asia/Shanghai")
ROOT = Path(os.environ.get("SKILLTO_TABLE_ROOT", str(Path.home() / "skillto-table-data")))
OUT = ROOT / "reports" / "raw" / "2026-11-07"
KEY = os.environ.get("TIKHUB_API_KEY")
MAX_CALLS = 500
MAX_PAGES = 50
CALLS = 0
LOCK = threading.Lock()


def now() -> str:
    return datetime.now(TZ).isoformat()


def call(endpoint: str, params: dict) -> dict:
    global CALLS
    with LOCK:
        if CALLS >= MAX_CALLS:
            raise RuntimeError("collection request cap reached")
        CALLS += 1
    url = "https://api.tikhub.io/api/v1/douyin/app/v3/" + endpoint + "?" + urlencode(params)
    request = Request(url, headers={"Authorization": "Bearer " + KEY, "User-Agent": "Mozilla/5.0"})
    last = None
    for attempt in range(2):
        try:
            with build_opener(ProxyHandler({})).open(request, timeout=60) as response:
                result = json.load(response)
            if result.get("code") == 200:
                return result.get("data") or {}
            last = RuntimeError("TikHub code " + str(result.get("code")))
        except Exception as exc:
            last = exc
        if attempt == 0:
            time.sleep(2)
    raise last


def roster() -> list[dict]:
    table = json.loads((ROOT / "tables" / (TABLE_ID + ".json")).read_text(encoding="utf-8"))
    tags = {item["name"]: item["id"] for item in table["tags"]}
    result = []
    for row in table["rows"]:
        group = next((name for name in GROUPS if tags[name] in row.get("tagIds", [])), None)
        if group:
            fields = row.get("fields") or {}
            result.append({"rowId": row["id"], "group": group, "accountName": fields.get("accountName"),
                           "secUid": fields.get("secUid"), "profileUrl": fields.get("profileUrl")})
    if len(result) != 74 or sum(x["group"] == GROUPS[0] for x in result) != 10:
        raise RuntimeError("tagged roster changed; review before collection")
    return result


def profile(item: dict) -> dict:
    result = {**item, "capturedAt": now(), "source": "TikHub douyin/app/v3/handler_user_profile",
              "followerCount": None, "totalFavorited": None, "error": None}
    try:
        data = call("handler_user_profile", {"sec_user_id": item["secUid"]})
        user = data.get("user") or {}
        if user.get("sec_uid") != item["secUid"]:
            raise RuntimeError("profile account mismatch")
        for field, source in (("followerCount", "follower_count"), ("totalFavorited", "total_favorited")):
            value = user.get(source)
            result[field] = value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
        result["capturedAt"] = now()
    except Exception as exc:
        result["error"] = type(exc).__name__ + ": " + str(exc)
    return result


def videos(item: dict) -> dict:
    result = {**item, "capturedAt": now(), "source": "TikHub douyin/app/v3/fetch_user_post_videos",
              "videos": [], "pages": 0, "complete": False, "error": None, "oldestPublishedAt": None}
    found = {}
    cursor = 0
    try:
        for page in range(MAX_PAGES):
            data = call("fetch_user_post_videos", {"sec_user_id": item["secUid"], "max_cursor": cursor,
                                                     "count": 20, "sort_type": 0, "channel": "normal"})
            result["pages"] += 1
            raw = data.get("aweme_list") or []
            oldest = None
            for entry in raw:
                author = entry.get("author") or {}
                video_id = entry.get("aweme_id")
                published = entry.get("create_time")
                if author.get("sec_uid") != item["secUid"] or not video_id or not isinstance(published, int):
                    continue
                local = datetime.fromtimestamp(published, TZ)
                date = local.date().isoformat()
                oldest = min(oldest, date) if oldest else date
                if not (START <= date < END):
                    continue
                stats = entry.get("statistics") or {}
                found[str(video_id)] = {
                    "id": str(video_id), "publishedAt": local.isoformat(), "capturedAt": now(),
                    "title": entry.get("desc") or "", "videoUrl": "https://www.douyin.com/video/" + str(video_id),
                    "likeCount": stats.get("digg_count"), "collectCount": stats.get("collect_count")}
            if oldest:
                result["oldestPublishedAt"] = oldest
            if oldest and oldest < START:
                result["complete"] = True
                break
            if not data.get("has_more"):
                result["complete"] = True
                break
            next_cursor = data.get("max_cursor")
            if not next_cursor or next_cursor == cursor:
                result["error"] = "pagination cursor stalled"
                break
            cursor = next_cursor
            if not raw:
                result["error"] = "empty page with has_more"
                break
        result["videos"] = sorted(found.values(), key=lambda x: x["publishedAt"], reverse=True)
    except Exception as exc:
        result["error"] = type(exc).__name__ + ": " + str(exc)
        result["videos"] = sorted(found.values(), key=lambda x: x["publishedAt"], reverse=True)
    return result


def save(name: str, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    if not KEY:
        raise SystemExit("TIKHUB_API_KEY is required")
    if now()[:10] != "2026-11-07":
        raise SystemExit("2026-11-07 snapshot collection window has closed")
    items = roster()
    if "--retry-incomplete" in sys.argv:
        saved = json.loads((OUT / "videos.json").read_text(encoding="utf-8"))
        incomplete = {p["rowId"] for p in saved if not p["complete"]}
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            repaired = {p["rowId"]: p for p in pool.map(videos, [item for item in items if item["rowId"] in incomplete])}
        posts = [repaired.get(p["rowId"], p) for p in saved]
        save("videos.json", posts)
        print("repaired", len(repaired), "complete", sum(p["complete"] for p in posts), "calls", CALLS, flush=True)
        return
    save("roster.json", {"sourceTableId": TABLE_ID, "frozenAt": now(), "accounts": items})
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        profiles = list(pool.map(profile, items))
    save("profiles.json", profiles)
    print("profiles", len(profiles), "complete", sum(p["followerCount"] is not None and p["totalFavorited"] is not None for p in profiles), flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        posts = list(pool.map(videos, items))
    save("videos.json", posts)
    print("video accounts", len(posts), "complete", sum(p["complete"] for p in posts),
          "videos", sum(len(p["videos"]) for p in posts), "calls", CALLS, flush=True)


if __name__ == "__main__":
    main()
