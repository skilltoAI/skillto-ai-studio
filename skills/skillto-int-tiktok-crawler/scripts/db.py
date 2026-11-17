from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from parser import utc_now

METRICS = ("view_count", "like_count", "comment_count", "collect_count", "share_count")


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version not in (0, 1):
        conn.close()
        raise ValueError("Unsupported TikTok database schema version.")
    conn.executescript("""
      CREATE TABLE IF NOT EXISTS accounts (
        user_id TEXT PRIMARY KEY, sec_uid TEXT NOT NULL UNIQUE, username TEXT NOT NULL,
        name TEXT, follower_count INTEGER, video_count INTEGER, avatar_url TEXT,
        last_crawled_at TEXT, last_status TEXT, last_coverage TEXT);
      CREATE TABLE IF NOT EXISTS videos (
        video_id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(user_id),
        author_user_id TEXT NOT NULL, author_sec_uid TEXT NOT NULL, title TEXT NOT NULL,
        topics TEXT NOT NULL, published_at TEXT NOT NULL, item_url TEXT NOT NULL,
        cover_url TEXT, media_url TEXT, duration INTEGER, updated_at TEXT NOT NULL,
        CHECK(account_id=author_user_id));
      CREATE INDEX IF NOT EXISTS videos_account_time ON videos(account_id,published_at);
      CREATE TABLE IF NOT EXISTS snapshots (
        video_id TEXT NOT NULL REFERENCES videos(video_id), snapshot_date TEXT NOT NULL,
        captured_at TEXT NOT NULL, view_count INTEGER, like_count INTEGER, comment_count INTEGER,
        collect_count INTEGER, share_count INTEGER, PRIMARY KEY(video_id,snapshot_date));
      CREATE TABLE IF NOT EXISTS crawl_runs (
        id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL,
        account_count INTEGER NOT NULL, success_count INTEGER NOT NULL DEFAULT 0,
        item_count INTEGER NOT NULL DEFAULT 0, error_count INTEGER NOT NULL DEFAULT 0,
        days INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS account_runs (
        id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES crawl_runs(id),
        username TEXT NOT NULL, account_id TEXT, started_at TEXT NOT NULL, finished_at TEXT NOT NULL,
        status TEXT NOT NULL, coverage TEXT NOT NULL, error_type TEXT,
        videos_seen INTEGER NOT NULL, saved_count INTEGER NOT NULL);
      PRAGMA user_version=1;
    """)
    return conn


def upsert_account(conn, profile: dict) -> None:
    keys = ("user_id", "sec_uid", "username", "name", "follower_count", "video_count", "avatar_url")
    conn.execute(f"INSERT INTO accounts ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)}) "
                 "ON CONFLICT(user_id) DO UPDATE SET sec_uid=excluded.sec_uid, username=excluded.username, "
                 "name=excluded.name, follower_count=COALESCE(excluded.follower_count,accounts.follower_count), "
                 "video_count=COALESCE(excluded.video_count,accounts.video_count), avatar_url=excluded.avatar_url",
                 [profile.get(k) for k in keys])


def save_video(conn, profile: dict, item: dict, captured_at: str | None = None) -> None:
    if item["author_user_id"] != profile["user_id"] or item["author_sec_uid"] != profile["sec_uid"]:
        raise ValueError("ownership_mismatch")
    existing = conn.execute("SELECT account_id FROM videos WHERE video_id=?", (item["video_id"],)).fetchone()
    if existing and existing[0] != profile["user_id"]:
        raise ValueError("ownership_mismatch")
    captured_at = captured_at or utc_now()
    keys = ("video_id", "author_user_id", "author_sec_uid", "title", "published_at", "item_url", "cover_url", "media_url", "duration")
    values = [item.get(k) for k in keys] + [profile["user_id"], json.dumps(item["topics"], ensure_ascii=False), captured_at]
    cols = (*keys, "account_id", "topics", "updated_at")
    updates = ",".join(f"{k}=excluded.{k}" for k in cols if k not in {"video_id", "account_id"})
    conn.execute(f"INSERT INTO videos ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)}) "
                 f"ON CONFLICT(video_id) DO UPDATE SET {updates}", values)
    cols = ("video_id", "snapshot_date", "captured_at", *METRICS)
    updates = ",".join(f"{k}=excluded.{k}" for k in ("captured_at", *METRICS))
    conn.execute(f"INSERT INTO snapshots ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)}) "
                 f"ON CONFLICT(video_id,snapshot_date) DO UPDATE SET {updates}",
                 [item["video_id"], captured_at[:10], captured_at, *[item.get(k) for k in METRICS]])


def latest_rows(conn, cutoff: str, until: str) -> list[dict]:
    return [dict(row) for row in conn.execute("""
      SELECT v.*,a.username,a.name AS account_name,a.follower_count,a.last_status,a.last_coverage,
             s.captured_at,s.view_count,s.like_count,s.comment_count,s.collect_count,s.share_count
      FROM videos v JOIN accounts a ON a.user_id=v.account_id
      JOIN snapshots s ON s.video_id=v.video_id
      WHERE v.author_user_id=a.user_id AND v.author_sec_uid=a.sec_uid
        AND v.published_at>=? AND v.published_at<=?
        AND s.snapshot_date=(SELECT MAX(s2.snapshot_date) FROM snapshots s2 WHERE s2.video_id=v.video_id)
      ORDER BY v.published_at DESC,v.video_id DESC
    """, (cutoff, until))]
