from __future__ import annotations

import html
import json
import sqlite3
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from analysis import summarize


def render(report: dict) -> str:
    def esc(value):
        return html.escape(str(value if value is not None else "—"), quote=True)

    accounts = "".join("<tr>" + "".join(f"<td>{esc(v)}</td>" for v in
                        (a["username"], a["follower_count"], a["item_count"], a["high_count"], a["last_status"], a["last_coverage"])) + "</tr>"
                        for a in report["accounts"])
    videos = ""
    for v in report["videos"]:
        link = f'<a href="{esc(v["item_url"])}" target="_blank" rel="noreferrer">{esc(v["title"] or v["video_id"])}</a>'
        videos += '<tr class="high">' if v["high_interaction"] else "<tr>"
        videos += f"<td>{esc(v['username'])}</td><td>{link}</td>" + "".join(f"<td>{esc(v[k])}</td>" for k in
                    ("published_at", "view_count", "like_count", "comment_count", "collect_count", "share_count"))
        videos += f"<td>{esc(', '.join(v['high_reasons']))}</td></tr>"
    runs = "".join("<tr>" + "".join(f"<td>{esc(r[k])}</td>" for k in
                    ("username", "finished_at", "status", "coverage", "error_type", "videos_seen", "saved_count")) + "</tr>"
                    for r in report["account_runs"])
    topics = "".join(f"<tr><td>{esc(t['topic'])}</td><td>{t['video_count']}</td><td>{t['high_count']}</td></tr>" for t in report["topics"])
    return f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>TikTok 内容分析</title>
<style>body{{font:15px system-ui;background:#f4f6fa;color:#182334;margin:32px}}h1{{font-size:30px}}
section{{background:white;border-radius:12px;padding:20px;margin:24px 0;overflow:auto}}
table{{border-collapse:collapse;width:100%}}td,th{{text-align:left;padding:10px;border-bottom:1px solid #e1e5ed;vertical-align:top}}
a{{color:#225dc4}}.high{{background:#fff3ce}}small{{color:#566477}}</style>
<h1>TikTok 内容分析</h1><p>近 {report['days']} 天 · {len(report['accounts'])} 个账号 · {len(report['videos'])} 条已采集内容</p>
<p><small>生成时间 UTC：{esc(report['generated_at'])}。黄色为收藏或分享严格大于本账号均值 2 倍；— 表示缺失。
partial / unknown 表示采集未证实完整，均值仅代表已采集样本。<a href="/api/report">下载 JSON 报告</a></small></p>
<section><h2>账号</h2><table><tr><th>账号</th><th>粉丝</th><th>内容数</th><th>高互动</th><th>状态</th><th>覆盖</th></tr>{accounts}</table></section>
<section><h2>内容与互动</h2><table><tr><th>账号</th><th>内容</th><th>发布时间 UTC</th><th>播放</th><th>赞</th><th>评论</th><th>收藏</th><th>分享</th><th>触发指标</th></tr>{videos}</table></section>
<section><h2>话题</h2><table><tr><th>话题</th><th>内容数</th><th>高互动数</th></tr>{topics}</table></section>
<section><h2>采集记录</h2><table><tr><th>账号</th><th>完成时间 UTC</th><th>状态</th><th>覆盖</th><th>错误</th><th>已见</th><th>保存</th></tr>{runs}</table></section></html>"""


def make_server(db_path, port=8878, days=30):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get("Host", "").split(":", 1)[0] not in {"127.0.0.1", "localhost"}:
                self.send_error(403)
                return
            path = urlparse(self.path).path
            if path not in {"/", "/api/report", "/health"}:
                self.send_error(404)
                return
            try:
                if path == "/health":
                    body, mime = b'{"status":"ok"}', "application/json"
                else:
                    with closing(sqlite3.connect(db_path)) as conn:
                        conn.row_factory = sqlite3.Row
                        report = summarize(conn, days)
                    body, mime = (json.dumps(report, ensure_ascii=False).encode(), "application/json") if path == "/api/report" else (render(report).encode(), "text/html")
                self.send_response(200)
                self.send_header("Content-Type", mime + "; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'")
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                self.send_error(500, "Report unavailable")

        def log_message(self, *_):
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)
