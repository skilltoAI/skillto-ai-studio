"""Create the two tagged teaching-account dashboards via the local report service."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import report_system as reports

TABLE_ID = "56fa8754-8d40-4225-8541-0be4729ade73"
GROUPS = ("AI付费流教学号", "AI自然流教学号")


def card(name, sql, db_id, display="table", description=""):
    result = {"name": name, "type": "question", "display": display,
              "visualization_settings": {},
              "dataset_query": {"database": db_id, "type": "native", "native": {"query": sql}}}
    if description:
        result["description"] = description
    return result


def queries(group, db_id):
    quoted = group.replace("'", "''")
    prefix = f"WHERE group_name = '{quoted}'"
    return [
        card("9—10月指标与覆盖", f"""SELECT to_char(month,'YYYY-MM') AS 月份,
            account_count AS 名单账号数, complete_accounts AS 完整覆盖账号数,
            observed_video_count AS 已见作品数, observed_like_count AS 已见点赞数,
            observed_collect_count AS 已见收藏数,
            videos_with_likes AS 有点赞指标作品数,
            videos_with_collects AS 有收藏指标作品数
            FROM group_month_metrics {prefix} ORDER BY month""", db_id,
            description="按北京时间发布时间分月；互动数为2026-11-07采集值。覆盖不完整时均为已观测数。"),
        card("月度作品数", f"""SELECT to_char(month,'YYYY-MM') AS 月份,
            observed_video_count AS 已见作品数
            FROM group_month_metrics {prefix} ORDER BY month""", db_id, "bar"),
        card("账号月度明细", f"""SELECT to_char(month,'YYYY-MM') AS 月份,
            account_name AS 账号,
            CASE coverage_status WHEN 'complete' THEN '完整' WHEN 'partial' THEN '部分' ELSE '不可得' END AS 覆盖状态,
            coverage_reason AS 未覆盖原因, video_count AS 已见作品数,
            like_count AS 已见点赞数, collect_count AS 已见收藏数,
            videos_with_likes AS 有点赞指标作品数,
            videos_with_collects AS 有收藏指标作品数, profile_url AS 主页
            FROM account_month_metrics {prefix}
            ORDER BY month, video_count DESC, account_name""", db_id),
        card("作品明细与来源", f"""SELECT a.account_name AS 账号,
            to_char(v.published_at AT TIME ZONE 'Asia/Shanghai','YYYY-MM-DD HH24:MI') AS 北京发布时间,
            v.title AS 作品, v.like_count AS 点赞数, v.collect_count AS 收藏数,
            v.video_url AS 原作品链接, v.captured_at AS 指标采集时间
            FROM video_observations v JOIN account_roster a ON a.row_id=v.account_row_id
            WHERE a.group_name = '{quoted}'
            ORDER BY v.published_at DESC""", db_id),
        card("11月7日账号主页快照", f"""SELECT a.account_name AS 账号,
            s.total_favorited AS 主页累计获赞, s.follower_count AS 粉丝数,
            CASE s.status WHEN 'complete' THEN '完整' ELSE '缺失' END AS 快照状态, s.reason AS 缺失原因,
            s.captured_at AS 采集时间, a.profile_url AS 主页
            FROM account_snapshots s JOIN account_roster a ON a.row_id=s.account_row_id
            WHERE a.group_name = '{quoted}' AND s.snapshot_date = '2026-11-07'
            ORDER BY a.account_name""", db_id),
    ]


def main():
    settings = reports.config()
    db_id = settings["metabaseDatabaseId"]
    catalog = reports.catalog()
    location = next(({"knowledgeBaseId": kb["id"], "projectId": project["id"]}
                     for kb in catalog["knowledgeBases"] for project in kb["projects"]
                     if any(t["id"] == TABLE_ID for t in project["tables"])), None)
    if not location:
        raise ValueError("account table location missing")
    for group in GROUPS:
        title = group + "｜2026年9—10月作品与11月7日快照"
        entry = next((r for r in catalog["reports"] if r["name"] == title and r["status"] == "active"), None)
        if not entry:
            entry = reports.create_report({**location, "name": title, "sourceTableId": TABLE_ID,
                "description": "2026-11-07名单。9、10月按发布时间统计；点赞、收藏为11月7日采集值。显示覆盖范围及缺失。"})
        existing_names = {reports.mb_request("GET", f"/api/card/{card_id}")["name"]: card_id
                          for card_id in entry["cardIds"]}
        for item in queries(group, db_id):
            if item["name"] in existing_names:
                reports.content({"operation": "update_card", "reportId": entry["id"],
                                 "cardId": existing_names[item["name"]], "card": item})
            else:
                reports.content({"operation": "create_card", "reportId": entry["id"], "card": item})
        dashboard = reports.mb_request("GET", f"/api/dashboard/{entry['metabaseDashboardId']}")
        cards = []
        for index, dashcard in enumerate(dashboard.get("dashcards") or []):
            cards.append({"id": dashcard["id"], "card_id": dashcard["card_id"],
                          "row": index * 6, "col": 0, "size_x": 24, "size_y": 6})
        if cards:
            reports.content({"operation": "update_dashboard", "reportId": entry["id"],
                             "dashboard": {"dashcards": cards}})
        reports.mb_request("PUT", f"/api/dashboard/{entry['metabaseDashboardId']}",
                           {"enable_embedding": True})
        print(group, "reportId", entry["id"], "dashboardId", entry["metabaseDashboardId"])


if __name__ == "__main__":
    main()
