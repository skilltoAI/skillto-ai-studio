from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from analysis import export_report, summarize
from auth import load_cookies
from crawler import crawl, doctor
from dashboard import make_server
from db import connect
from parser import account_from_mapping, load_accounts
from keywords import write_expansion
from search import search
from detail import collect_videos
from pacing import pacer_for


def positive(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Must be a positive integer.")
    return number


def nonnegative(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("Must be zero or a positive integer.")
    return number


def build_parser():
    parser = argparse.ArgumentParser(description="Authorized TikTok profile capture and local content analysis.")
    sub = parser.add_subparsers(dest="command", required=True)
    keywords = sub.add_parser("keywords")
    keywords.add_argument("--keyword", action="append", required=True)
    keywords.add_argument("--languages", default="en,ja,de,fr")
    keywords.add_argument("--output", type=Path, required=True)
    for command in ("crawl", "update", "analyze", "serve", "doctor", "search", "video"):
        p = sub.add_parser(command)
        if command != "doctor":
            p.add_argument("--db", type=Path, default=Path("data/tiktok.sqlite3"))
            p.add_argument("--days", type=positive, default=30, help="Rolling publish-time window, UTC.")
        if command in {"crawl", "update", "search", "video"}:
            if command not in {"search", "video"}:
                source = p.add_mutually_exclusive_group(required=True)
                source.add_argument("--accounts", type=Path, help="JSON/CSV/TXT account list.")
                source.add_argument("--account", action="append", help="Profile URL or @handle; repeatable.")
            p.add_argument("--cookies", type=Path)
            p.add_argument("--limit", type=positive)
            p.add_argument("--max-scrolls", type=positive, default=50)
            p.add_argument("--wait-ms", type=positive, default=3500)
            p.add_argument("--timeout", type=positive, default=45, help="Navigation timeout in seconds.")
            p.add_argument("--account-delay", type=positive, default=8, help="Seconds between serial queries/accounts/video pages.")
            p.add_argument("--checkpoint", type=Path, default=Path(f"runtime/tiktok-{command}-checkpoint.json"))
            p.add_argument("--resume", action="store_true", help="Resume pending targets and the saved backoff deadline.")
            p.add_argument("--no-manual-challenge", action="store_true", help="Stop on CAPTCHA instead of opening a visible browser for manual completion.")
            p.add_argument("--challenge-wait", type=nonnegative, default=0, help="Manual verification timeout in seconds; 0 (default) waits until solved or cancelled.")
        if command == "video":
            p.add_argument("--url", action="append", required=True)
            p.add_argument("--report", type=Path, default=Path("data/tiktok-video-report.json"))
        if command == "search":
            p.add_argument("--keyword", action="append", required=True)
            p.add_argument("--languages", default="en,ja,de,fr")
            p.add_argument("--queries", type=Path, help="Optional JSON query list or keyword expansion file.")
            p.add_argument("--min-videos", type=positive, default=1000)
            p.add_argument("--max-queries", type=positive)
            p.add_argument("--all-queries", action="store_true", help="Run the entire supplied query list even after the minimum sample target is met.")
            p.add_argument("--verify-top", type=positive, help="Verify this many recent candidates by views, plus all low-follower candidates with returned follower data.")
            p.add_argument("--max-authors", type=positive, default=1000)
            p.add_argument("--top", type=positive, default=50)
            p.add_argument("--max-followers", type=positive, default=10000)
            p.add_argument("--min-views", type=positive, default=100000)
            p.add_argument("--min-ratio", type=float, default=10)
            p.add_argument("--interactive-wait", type=int, default=0, help="Keep an empty headed search page open for manual login, seconds.")
            p.add_argument("--report", type=Path, default=Path("data/tiktok-search-report.json"))
        if command in {"crawl", "update", "doctor", "search", "video"}:
            p.add_argument("--headed", action="store_true")
            browser = p.add_mutually_exclusive_group()
            browser.add_argument("--browser-channel", choices=("chrome", "msedge", "chromium"))
            browser.add_argument("--browser-executable")
        if command in {"crawl", "update", "analyze"}:
            p.add_argument("--report", type=Path, help="Full analysis JSON, includes coverage and errors.")
            p.add_argument("--jsonl", type=Path)
            p.add_argument("--csv", type=Path)
        if command == "serve":
            p.add_argument("--port", type=positive, default=8878)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "keywords":
        result = write_expansion(args.output, args.keyword, args.languages.split(","))
        print(json.dumps({"queries": len(result["queries"]), "languages": result["languages"]}))
        return 0
    if args.command == "doctor":
        asyncio.run(doctor(args))
        return 0
    cookies = None
    if args.command in {"crawl", "update", "search", "video"}:
        # Validate cookie/targets before creating a database.
        cookies = load_cookies(args.cookies)
        if args.command not in {"search", "video"}:
            accounts = load_accounts(args.accounts) if args.accounts else [account_from_mapping(a) for a in args.account]
            accounts = accounts[:args.limit] if args.limit else accounts
    elif not args.db.is_file():
        raise ValueError("Database does not exist; crawl first or select an existing --db.")
    conn = connect(args.db)
    try:
        if args.command == "search":
            return asyncio.run(search(args, cookies, conn))
        if args.command == "video":
            return asyncio.run(collect_videos(args, cookies, conn))
        if args.command == "serve":
            conn.close()
            with make_server(args.db.resolve(), args.port, args.days) as server:
                print(f"TikTok dashboard: http://127.0.0.1:{server.server_port}", flush=True)
                server.serve_forever()
            return 0
        results = asyncio.run(crawl(accounts, cookies, args, conn)) if cookies is not None else []
        report = summarize(conn, args.days)
        if cookies is not None:
            pacer = pacer_for(args)
            report["pacing"] = pacer.snapshot()
        export_report(report, report_path=args.report, jsonl=args.jsonl, csv_path=args.csv)
        print(json.dumps({"accounts": len(report["accounts"]), "videos": len(report["videos"]),
                          "high_interaction": sum(v["high_interaction"] for v in report["videos"]),
                          "window_days": args.days, "coverage": {a["username"]: a["last_coverage"] for a in report["accounts"]}}))
        return 2 if any(r["status"] == "failed" for r in results) else 3 if any(r["status"] == "partial" for r in results) else 0
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except (ValueError, OSError) as exc:
        print(str(exc) if isinstance(exc, ValueError) else "Operation failed; check paths, permissions, or port availability.", file=sys.stderr)
        raise SystemExit(2)
