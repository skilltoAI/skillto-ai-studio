"""Export reviewable CSV copies of the frozen report values."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import psycopg

ROOT = Path(os.environ.get("SKILLTO_TABLE_ROOT", str(Path.home() / "skillto-table-data")))
CONFIG = Path(os.environ.get("SKILLTO_REPORT_CONFIG", str(Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SkillToTable" / "reporting" / "config.json")))
OUT = ROOT / "reports" / "exports" / "2026-11-07"

QUERIES = {
    "monthly_summary.csv": """SELECT group_name AS 账号分类, to_char(month,'YYYY-MM') AS 月份,
        account_count AS 名单账号数,complete_accounts AS 完整覆盖账号数,
        observed_video_count AS 作品数,observed_like_count AS 点赞数,
        observed_collect_count AS 收藏数 FROM group_month_metrics ORDER BY group_name,month""",
    "account_monthly.csv": """SELECT group_name AS 账号分类,account_name AS 账号,
        to_char(month,'YYYY-MM') AS 月份,coverage_status AS 覆盖状态,
        coverage_reason AS 覆盖说明,video_count AS 作品数,like_count AS 点赞数,
        collect_count AS 收藏数,profile_url AS 主页 FROM account_month_metrics
        ORDER BY group_name,account_name,month""",
    "account_snapshots.csv": """SELECT a.group_name AS 账号分类,a.account_name AS 账号,
        s.total_favorited AS 主页累计获赞,s.follower_count AS 粉丝数,
        s.captured_at AS 采集时间,s.status AS 快照状态,
        s.reason AS 缺失原因,a.profile_url AS 主页
        FROM account_snapshots s JOIN account_roster a ON a.row_id=s.account_row_id
        WHERE s.snapshot_date='2026-11-07' ORDER BY a.group_name,a.account_name""",
}


def main():
    settings = json.loads(CONFIG.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    with psycopg.connect(host="127.0.0.1", port=5434, dbname="reports",
                         user="report_admin", password=settings["dbPassword"]) as db:
        for name, query in QUERIES.items():
            with db.cursor() as cur:
                cur.execute(query)
                headers = [column.name for column in cur.description]
                rows = cur.fetchall()
            with (OUT / name).open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(headers)
                writer.writerows(rows)
            print(name, len(rows))


if __name__ == "__main__":
    main()
