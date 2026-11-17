"""Normalize known TikTok web payloads; never infer an author from a URL alone."""
from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def count(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([kmb]?)", str(value).strip().replace(",", "").lower())
    if not match:
        return None
    number = float(match[1]) * {"": 1, "k": 1000, "m": 1000000, "b": 1000000000}[match[2]]
    return int(number) if math.isfinite(number) and number <= 2**63 - 1 else None


def timestamp(value) -> str | None:
    number = count(value)
    if not number:
        return None
    if number > 10_000_000_000:
        number /= 1000
    try:
        return datetime.fromtimestamp(number, timezone.utc).isoformat(timespec="seconds")
    except (ValueError, OverflowError, OSError):
        return None


def first(obj: dict, *names):
    for name in names:
        value = obj
        for key in name.split("."):
            value = value.get(key) if isinstance(value, dict) else None
        if value is not None:
            return value
    return None


def media_url(value) -> str | None:
    if isinstance(value, str) and value.startswith("https://"):
        return value
    if isinstance(value, list):
        return next((url for v in value if (url := media_url(v))), None)
    if isinstance(value, dict):
        return media_url(first(value, "urlList", "url_list", "url"))
    return None


@dataclass(frozen=True)
class Account:
    username: str
    name: str = ""
    user_id: str = ""
    sec_uid: str = ""

    @property
    def url(self):
        return f"https://www.tiktok.com/@{self.username}"


def account_from_mapping(row) -> Account:
    if isinstance(row, str):
        row = {"url": row} if "://" in row else {"username": row}
    if not isinstance(row, dict) or row.get("platform", "tiktok").lower() != "tiktok":
        raise ValueError("Account rows must describe TikTok accounts.")
    username = str(row.get("username") or row.get("uniqueId") or "").lstrip("@").strip()
    url = row.get("url") or row.get("profile_url")
    if url:
        parsed = urlparse(str(url))
        match = re.fullmatch(r"/@([\w.]{1,24})/?", unquote(parsed.path), flags=re.ASCII)
        if parsed.scheme != "https" or parsed.netloc.lower() not in {"www.tiktok.com", "tiktok.com"} or not match:
            raise ValueError("Use an HTTPS TikTok /@username profile URL (no short links).")
        if username and username.casefold() != match[1].casefold():
            raise ValueError("Username conflicts with profile URL.")
        username = match[1]
    if not re.fullmatch(r"[\w.]{1,24}", username, flags=re.ASCII):
        raise ValueError("A TikTok username or canonical profile URL is required.")
    user_id = str(row.get("user_id") or row.get("account_id") or "")
    if user_id and not user_id.isdigit():
        raise ValueError("user_id/account_id must be the numeric TikTok user id, not a handle or secUid.")
    return Account(username, str(row.get("name") or username), user_id, str(row.get("sec_uid") or row.get("secUid") or ""))


def load_accounts(path: Path) -> list[Account]:
    if path.suffix.lower() == ".json":
        rows = json.loads(path.read_text(encoding="utf-8-sig"))
        rows = rows.get("accounts") if isinstance(rows, dict) else rows
    elif path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    else:
        rows = []
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            fields = next(csv.reader([line]))
            rows.append({"name": fields[0], "url": fields[1]} if len(fields) == 2 else fields[0])
    if not isinstance(rows, list) or not rows:
        raise ValueError("Account list must be a nonempty JSON array, CSV, or TXT file.")
    accounts = [account_from_mapping(row) for row in rows]
    if len({a.username.casefold() for a in accounts}) != len(accounts):
        raise ValueError("Duplicate usernames in account list.")
    return accounts


def profile_candidates(payload: dict) -> list[dict]:
    candidates = []
    scope = payload.get("__DEFAULT_SCOPE__", {})
    for value in (payload, payload.get("data"), scope.get("webapp.user-detail")):
        if isinstance(value, dict) and isinstance(value.get("userInfo"), dict):
            candidates.append(value["userInfo"])
    module = payload.get("UserModule", {})
    for key, user in module.get("users", {}).items():
        if isinstance(user, dict):
            candidates.append({"user": user, "stats": module.get("stats", {}).get(key, {})})
    return candidates


def parse_profile(payload: dict, account: Account) -> dict | None:
    for info in profile_candidates(payload):
        user = info.get("user", {})
        if str(user.get("uniqueId", "")).casefold() != account.username.casefold():
            continue
        uid, sec = str(user.get("id") or ""), str(user.get("secUid") or "")
        if not uid.isdigit() or not sec:
            continue
        if (account.user_id and account.user_id != uid) or (account.sec_uid and account.sec_uid != sec):
            raise ValueError("identity_mismatch")
        return dict(user_id=uid, sec_uid=sec, username=user["uniqueId"], name=user.get("nickname") or account.name,
                    follower_count=count(first(info, "stats.followerCount", "statsV2.followerCount")),
                    video_count=count(first(info, "stats.videoCount", "statsV2.videoCount")),
                    avatar_url=media_url(first(user, "avatarLarger", "avatarMedium", "avatarThumb")))
    return None


def item_candidates(payload: dict) -> list[dict]:
    result = []
    for key in ("itemList", "item_list"):
        items = payload.get(key)
        if isinstance(items, list):
            result.extend(item for item in items if isinstance(item, dict))
    data = payload.get("data")
    if isinstance(data, dict):
        result.extend(item_candidates(data))
    module = payload.get("ItemModule")
    if isinstance(module, dict):
        result.extend(item for item in module.values() if isinstance(item, dict))
    return result


def parse_item(raw: dict, profile: dict) -> dict | None:
    author = raw.get("author")
    if not isinstance(author, dict):
        # SIGI_STATE has a handle here, with stable IDs alongside it.
        author = dict(uniqueId=author, id=raw.get("authorId"), secUid=raw.get("authorSecId"))
    uid, sec = str(author.get("id") or ""), str(author.get("secUid") or "")
    # Every supplied stable identifier must agree; at least one is required.
    if not (uid or sec) or (uid and uid != profile["user_id"]) or (sec and sec != profile["sec_uid"]):
        return None
    video_id = str(raw.get("id") or "")
    published = timestamp(first(raw, "createTime", "create_time"))
    if not video_id.isdigit() or not published:
        return None
    title = str(raw.get("desc") or "")
    topics = list(dict.fromkeys(re.findall(r"#([\w.]+)", title)))
    for tag in raw.get("textExtra") or []:
        if isinstance(tag, dict) and tag.get("hashtagName") and tag["hashtagName"] not in topics:
            topics.append(tag["hashtagName"])
    stats = raw.get("statsV2") if isinstance(raw.get("statsV2"), dict) else {}
    stats = {**(raw.get("stats") or {}), **stats}
    return dict(video_id=video_id, author_user_id=profile["user_id"], author_sec_uid=profile["sec_uid"],
                title=title, topics=topics, published_at=published,
                item_url=f"https://www.tiktok.com/@{profile['username']}/video/{video_id}",
                cover_url=media_url(first(raw, "video.cover", "video.originCover", "video.dynamicCover")),
                media_url=media_url(first(raw, "video.playAddr", "video.downloadAddr")),
                duration=count(first(raw, "video.duration")),
                view_count=count(first(stats, "playCount", "viewCount")),
                like_count=count(stats.get("diggCount")), comment_count=count(stats.get("commentCount")),
                collect_count=count(first(stats, "collectCount", "favoritesCount")),
                share_count=count(stats.get("shareCount")))
