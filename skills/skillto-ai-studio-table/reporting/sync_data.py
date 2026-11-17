"""Load the frozen 2026-11-07 observations into the Metabase query database."""
from __future__ import annotations

import json
import os
from pathlib import Path

import psycopg

ROOT = Path(os.environ.get("SKILLTO_TABLE_ROOT", str(Path.home() / "skillto-table-data")))
RAW = ROOT / "reports" / "raw" / "2026-11-07"
CONFIG = Path(os.environ.get("SKILLTO_REPORT_CONFIG", str(Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SkillToTable" / "reporting" / "config.json")))

SCHEMA = """
CREATE TABLE IF NOT EXISTS account_roster (
  row_id text PRIMARY KEY, group_name text NOT NULL, account_name text NOT NULL,
  sec_uid text NOT NULL UNIQUE, profile_url text, source_table_id text NOT NULL,
  frozen_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS video_observations (
  video_id text PRIMARY KEY, account_row_id text NOT NULL REFERENCES account_roster(row_id),
  published_at timestamptz NOT NULL, captured_at timestamptz NOT NULL,
  title text, video_url text, like_count bigint, collect_count bigint,
  source text NOT NULL
);
CREATE TABLE IF NOT EXISTS account_month_coverage (
  account_row_id text NOT NULL REFERENCES account_roster(row_id), month date NOT NULL,
  status text NOT NULL, reason text, pages integer NOT NULL,
  captured_at timestamptz NOT NULL, PRIMARY KEY(account_row_id, month)
);
CREATE TABLE IF NOT EXISTS account_snapshots (
  account_row_id text NOT NULL REFERENCES account_roster(row_id), snapshot_date date NOT NULL,
  follower_count bigint, total_favorited bigint, captured_at timestamptz,
  source text, status text NOT NULL, reason text,
  PRIMARY KEY(account_row_id, snapshot_date)
);
CREATE OR REPLACE VIEW account_month_metrics AS
SELECT a.group_name, a.row_id AS account_row_id, a.account_name, a.profile_url,
       c.month, c.status AS coverage_status, c.reason AS coverage_reason,
       count(v.video_id)::int AS video_count,
       sum(v.like_count) AS like_count, sum(v.collect_count) AS collect_count,
       count(v.like_count)::int AS videos_with_likes,
       count(v.collect_count)::int AS videos_with_collects
FROM account_roster a
JOIN account_month_coverage c ON c.account_row_id=a.row_id
LEFT JOIN video_observations v ON v.account_row_id=a.row_id
  AND (v.published_at AT TIME ZONE 'Asia/Shanghai')::date >= c.month
  AND (v.published_at AT TIME ZONE 'Asia/Shanghai')::date < (c.month + INTERVAL '1 month')::date
GROUP BY a.group_name,a.row_id,a.account_name,a.profile_url,c.month,c.status,c.reason;
CREATE OR REPLACE VIEW group_month_metrics AS
SELECT group_name, month, count(*)::int AS account_count,
       count(*) FILTER (WHERE coverage_status='complete')::int AS complete_accounts,
       sum(video_count)::int AS observed_video_count,
       sum(like_count) AS observed_like_count,
       sum(collect_count) AS observed_collect_count,
       sum(videos_with_likes)::int AS videos_with_likes,
       sum(videos_with_collects)::int AS videos_with_collects
FROM account_month_metrics GROUP BY group_name,month;
"""


def main():
    settings = json.loads(CONFIG.read_text(encoding="utf-8"))
    frozen = json.loads((RAW / "roster.json").read_text(encoding="utf-8"))
    profiles = {p["rowId"]: p for p in json.loads((RAW / "profiles.json").read_text(encoding="utf-8"))}
    posts = {p["rowId"]: p for p in json.loads((RAW / "videos.json").read_text(encoding="utf-8"))}
    if len(frozen["accounts"]) != 74:
        raise ValueError("frozen roster must contain 74 accounts")
    lineage = {
        "sourceTableId": frozen["sourceTableId"],
        "sources": "本地账号合并表中2026-11-07冻结的AI付费流教学号与AI自然流教学号标签；TikHub抖音账号主页和账号作品列表，采集于2026-11-07北京时间。",
        "methods": "按账号sec_uid核验主页，按作品ID去重，分页采集至早于2026-09-01或无后续页；保存原始采集时间、分页覆盖与错误。主页累计获赞和粉丝数独立采集。",
        "rules": "统计2026-09-01至2026-10-31北京时间发布的作品；点赞和收藏使用2026-11-07采集值，不是月末值。缺失指标为NULL，不作零。每个账号月份保存完整、部分或不可得覆盖状态。",
        "destinations": "本机PostgreSQL reports数据库供Metabase仪表板查询；本地8880报表工作台显示。原账号表不被回写；不自动同步AMD-PAD。",
        "frozenAt": frozen["frozenAt"],
    }
    with psycopg.connect(host="127.0.0.1", port=5434, dbname="reports",
                         user="report_admin", password=settings["dbPassword"]) as db:
        with db.cursor() as cur:
            cur.execute(SCHEMA)
            for account in frozen["accounts"]:
                row_id = account["rowId"]
                cur.execute("""INSERT INTO account_roster VALUES (%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (row_id) DO UPDATE SET group_name=EXCLUDED.group_name,
                    account_name=EXCLUDED.account_name, profile_url=EXCLUDED.profile_url""",
                    (row_id, account["group"], account["accountName"] or "", account["secUid"],
                     account.get("profileUrl"), frozen["sourceTableId"], frozen["frozenAt"]))
                profile = profiles.get(row_id) or {}
                captured = profile.get("capturedAt")
                valid = bool(captured and captured[:10] == "2026-11-07"
                             and profile.get("followerCount") is not None
                             and profile.get("totalFavorited") is not None)
                cur.execute("""INSERT INTO account_snapshots VALUES (%s,'2026-11-07',%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (account_row_id,snapshot_date) DO UPDATE SET
                    follower_count=CASE WHEN account_snapshots.status='complete' THEN account_snapshots.follower_count ELSE EXCLUDED.follower_count END,
                    total_favorited=CASE WHEN account_snapshots.status='complete' THEN account_snapshots.total_favorited ELSE EXCLUDED.total_favorited END,
                    captured_at=CASE WHEN account_snapshots.status='complete' THEN account_snapshots.captured_at ELSE EXCLUDED.captured_at END,
                    source=CASE WHEN account_snapshots.status='complete' THEN account_snapshots.source ELSE EXCLUDED.source END,
                    status=CASE WHEN account_snapshots.status='complete' THEN account_snapshots.status ELSE EXCLUDED.status END,
                    reason=CASE WHEN account_snapshots.status='complete' THEN account_snapshots.reason ELSE EXCLUDED.reason END""",
                    (row_id, profile.get("followerCount") if valid else None,
                     profile.get("totalFavorited") if valid else None,
                     captured if valid else None, profile.get("source") if valid else None,
                     "complete" if valid else "missing", None if valid else profile.get("error") or "11月7日主页指标缺失"))
                observation = posts.get(row_id) or {}
                for month in ("2026-09-01", "2026-10-01"):
                    complete = bool(observation.get("complete") and str(observation.get("capturedAt", ""))[:10] == "2026-11-07")
                    status = "complete" if complete else "partial" if observation.get("videos") else "unavailable"
                    cur.execute("""INSERT INTO account_month_coverage VALUES (%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (account_row_id,month) DO UPDATE SET
                        status=EXCLUDED.status, reason=EXCLUDED.reason,pages=EXCLUDED.pages,captured_at=EXCLUDED.captured_at""",
                        (row_id, month, status, None if complete else observation.get("error") or "分页未覆盖全月",
                         observation.get("pages", 0), observation.get("capturedAt") or frozen["frozenAt"]))
                for video in observation.get("videos") or []:
                    likes, collects = video.get("likeCount"), video.get("collectCount")
                    cur.execute("""INSERT INTO video_observations VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (video_id) DO UPDATE SET
                        captured_at=EXCLUDED.captured_at,like_count=EXCLUDED.like_count,
                        collect_count=EXCLUDED.collect_count,title=EXCLUDED.title""",
                        (video["id"], row_id, video["publishedAt"], video["capturedAt"],
                         video.get("title"), video.get("videoUrl"),
                         likes if isinstance(likes, int) and not isinstance(likes, bool) else None,
                         collects if isinstance(collects, int) and not isinstance(collects, bool) else None,
                         observation.get("source") or "TikHub"))
    (ROOT / "reports" / "lineage.json").write_text(json.dumps(lineage, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Synced 74 accounts, 148 coverage rows, 74 snapshots,",
          sum(len(p.get("videos") or []) for p in posts.values()), "videos")


if __name__ == "__main__":
    main()
