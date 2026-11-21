from __future__ import annotations

import csv
import json
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

from db import METRICS, latest_rows


def summarize(conn, days: int = 30, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=days)).isoformat(timespec="seconds")
    until = now.isoformat(timespec="seconds")
    videos = latest_rows(conn, cutoff, until)
    groups = {a["user_id"]: {**dict(a), "items": []} for a in conn.execute("SELECT * FROM accounts ORDER BY username")}
    for video in videos:
        video["topics"] = json.loads(video["topics"])
        groups[video["account_id"]]["items"].append(video)
    accounts = []
    topics: dict[str, dict] = {}
    for uid, group in groups.items():
        items = group.pop("items")
        means = {}
        counts = {}
        for metric in METRICS:
            observed = [v[metric] for v in items if v[metric] is not None]
            means[metric] = statistics.mean(observed) if observed else None
            counts[metric] = len(observed)
        for v in items:
            v["high_reasons"] = [m for m in ("collect_count", "share_count")
                                 if v[m] is not None and means[m] is not None and v[m] > 2 * means[m]]
            v["high_interaction"] = bool(v["high_reasons"])
            for metric in ("collect_count", "share_count"):
                v[metric + "_ratio"] = v[metric] / means[metric] if v[metric] is not None and means[metric] else None
            # NULL when the numerator is incomplete; collection counts are not mixed into this rate.
            needed = (v["like_count"], v["comment_count"], v["share_count"])
            v["engagement_rate_by_views"] = sum(needed) / v["view_count"] if v["view_count"] and all(n is not None for n in needed) else None
            for tag in v["topics"]:
                topic = topics.setdefault(tag, {"topic": tag, "video_count": 0, "observed_views": 0, "view_sample_count": 0, "high_count": 0})
                topic["video_count"] += 1
                topic["high_count"] += int(v["high_interaction"])
                if v["view_count"] is not None:
                    topic["observed_views"] += v["view_count"]
                    topic["view_sample_count"] += 1
        accounts.append({**group, "item_count": len(items), "means": means, "sample_counts": counts,
                         "high_count": sum(v["high_interaction"] for v in items)})
    runs = [dict(r) for r in conn.execute("SELECT * FROM crawl_runs ORDER BY id DESC LIMIT 30")]
    errors = [dict(r) for r in conn.execute("SELECT * FROM account_runs ORDER BY id DESC LIMIT 100")]
    return dict(generated_at=until, cutoff=cutoff, days=days, rule="collect_count > 2 * account mean OR share_count > 2 * account mean",
                accounts=accounts, videos=videos, topics=sorted(topics.values(), key=lambda t: t["video_count"], reverse=True),
                runs=runs, account_runs=errors,
                limitations=["Averages describe captured items only; inspect last_coverage and account_runs.",
                             "Missing metrics are NULL; incomplete engagement numerators produce NULL.",
                             "Snapshots are UTC daily observations, not historical backfills; signed media URLs may expire."])


def safe_cell(value):
    if isinstance(value, (list, dict)):
        value = json.dumps(value, ensure_ascii=False)
    # Spreadsheet formula injection protection; raw JSON keeps original text.
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        value = "'" + value
    return value


def export_report(report: dict, *, report_path: Path | None = None, jsonl: Path | None = None, csv_path: Path | None = None) -> None:
    for path in (report_path, jsonl, csv_path):
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
    if report_path:
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if jsonl:
        jsonl.write_text("".join(json.dumps(v, ensure_ascii=False) + "\n" for v in report["videos"]), encoding="utf-8")
    if csv_path:
        fields = list(report["videos"][0]) if report["videos"] else ["video_id", "username", "title", "published_at", *METRICS]
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows({k: safe_cell(v) for k, v in video.items()} for video in report["videos"])
