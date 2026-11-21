---
name: skillto-ai-studio-tiktok-crawler
description: Collect authorized TikTok profile and keyword-search video data, expand multilingual pet-content keywords, and analyze recent popularity or low-follower viral content with SQLite and report-table exports.
---

# Skillto-AI-Studio · TikTok 采集

Use the bundled Python CLI for repeatable TikTok account collection and keyword research. Like `skillto-ai-studio-douyin-xhs-crawler`, it defaults to a headless Playwright browser: no visible browser window and no dashboard needs to be opened. It loads normal pages in the background and observes their ordinary JSON responses, rather than making independently signed API calls. The web endpoint shapes are provisional and must be checked against the current page.

## Session and collection rules

- Use only the user-authorized TikTok cookie/session. Resolve `--cookies`, then `TIKTOK_COOKIE_FILE`, then the platform default in [cookie setup](references/cookie-setup.md). Do not search unrelated runtime folders, reuse Douyin credentials, or change login accounts silently.
- Keep cookies, browser state and authorization headers outside source control and reports. Do not log request URLs, raw browser errors, or full hydration objects, which may contain session data. Use `scripts/configure_cookie.py` for hidden input and private file permissions.
- Observe normal page navigation and scrolling. Do not sign/replay internal APIs, install stealth plugins, rotate proxies, or bypass login, CAPTCHAs, private accounts, access restrictions or rate limits. On CAPTCHA or a login verification gate, save pending progress and open a visible browser with the same authorized session for the human to complete verification. Default `--challenge-wait 0` waits until solved or explicitly cancelled; no automatic 15-minute timeout. Transfer updated cookies in memory and recheck the background page before continuing. `--no-manual-challenge` explicitly disables this handoff.
- Keep collection serial. Default scroll wait is 3.5 seconds and the normal task interval is 8 seconds. Consecutive transient data anomalies use random waits: **1: 1–5 seconds; 2: 5–20 seconds; 3: 20–60 seconds; 4: 1–3 minutes; 5: 3–10 minutes; 6 and later: 10–60 minutes**. Retry the same pending query/account/video/author after waiting, with a slower cadence; do not abandon the task at the third or sixth failure. Three healthy results gradually restore the normal cadence; usable duplicates and explicit pagination exhaustion are healthy. HTTP 429 uses the longest tier and respects any longer `Retry-After`. Explicit access denial or an unresolved human gate requires attention with progress retained; identity conflicts and private targets are recorded separately and do not become fake successful results. See [pacing and manual verification](references/pacing.md).
- **Make waiting visible.** Before a pause report its reason, consecutive count/tier, selected duration, resume time, pending item and collected progress. Emit a countdown/status at least every 30 seconds during long waits and announce resumption. Relay these events to the user when operating the CLI; do not go silent or report a scheduled wait as task completion. Save the checkpoint before waiting. On `--resume`, retain pending work, error streak, slowdown and any remaining wait. Continue until the requested completion condition is fulfilled; do not silently lower sample targets, skip transiently failing items, or claim unavailable data was collected.
- For account capture, match the requested handle to profile JSON and pin its numeric user id plus `secUid`. Require the item's stable author identifiers to agree before saving; reject conflicting supplied IDs. Later runs pin the stored identity to detect handle reuse. Recommendations and other users' posts must not enter account statistics.
- For search discovery, retain each video's stable author IDs and query provenance. Verify the author's profile before promoting a row into ranked results or SQLite. Search hits alone do not establish AI generation, content relevance, creator region, or language.
- Save covers and media URLs; download media only when separately requested. Signed URLs can expire. A source video-page link is not a playable MP4 URL.

## Setup and profile capture

Use Python 3.10+ and an existing project environment where possible:

```powershell
python -m pip install -r <skill-root>/scripts/requirements.txt
python <skill-root>/scripts/run.py doctor --browser-channel msedge
python <skill-root>/scripts/configure_cookie.py
python <skill-root>/scripts/run.py crawl --account https://www.tiktok.com/@example --browser-channel msedge --db data/tiktok.sqlite3 --report data/report.json --csv data/videos.csv --jsonl data/videos.jsonl
```

Use `chrome` on machines with Chrome, or omit the channel after `python -m playwright install chromium`. `doctor` tests browser launch only, not session validity. Omit `--headed` for routine background collection; add it only to show a window for the entire diagnostic run. `--browser-executable` selects a specific installed browser. No machine-specific Python or browser executable is embedded.

`--accounts` accepts JSON/CSV/TXT lists instead of repeated `--account` arguments. For formats, payload aliases, identity checks and database semantics read [capture and schema](references/capture-and-schema.md). `--days` defaults to 30 by publish time, `--limit` bounds account diagnostics, `--max-scrolls` bounds a page attempt. Transient errors retry the pending account with backoff; permanent target errors are recorded and other accounts continue. All collection commands support `--checkpoint` and `--resume`.

For a specific source video, use `python <skill-root>/scripts/run.py video --url https://www.tiktok.com/@example/video/123456789 --report data/video-report.json`; repeat `--url` for a bounded list. It reads the ordinary video page's `webapp.video-detail.itemInfo.itemStruct` or bound `/api/item/detail/` response, then verifies the author profile before saving. This helps verify originals found through trend research. Keep these explicit source pages separate from the keyword-search sample count.

```powershell
python <skill-root>/scripts/run.py analyze --db data/tiktok.sqlite3 --report data/report.json
python <skill-root>/scripts/run.py serve --db data/tiktok.sqlite3 --port 8878
```

`update` accepts the same arguments as `crawl` and performs capture plus analysis. `serve` binds only to `127.0.0.1`. The dashboard shows accounts, videos, topics, metrics, coverage and failed runs; it is read-only. For editable multimedia review tables use the user's installed `skillto-table` or `skillto-ai-studio-table` as described below.

## Keyword research and 1,000-video validation

Read [keyword research and ranking](references/keyword-research.md) before discovery, multilingual expansion, or low-follower analysis.

```powershell
python <skill-root>/scripts/run.py keywords --keyword "AI dog" --keyword "AI cat" --languages en,ja,de,fr --output data/keywords.json
python <skill-root>/scripts/run.py search --keyword "AI dog" --keyword "AI cat" --languages en,ja,de,fr --min-videos 1000 --browser-channel msedge --checkpoint runtime/tiktok-search-checkpoint.json --report data/search-report.json --db data/tiktok.sqlite3
```

Search expansions are linguistic proposals, not measured popular queries or verified meme names. `--queries` accepts a reviewed JSON query list. `--resume` reloads a checkpoint for the same subject, options and authorized session. `--interactive-wait 900` optionally leaves an empty headed search page available for diagnostics; it is separate from the default unlimited manual CAPTCHA wait. If all healthy queries exhaust before the sample target is met, review/expand the query list and continue collection; repeated already-exhausted results cannot establish a larger unique sample. A genuine access denial remains pending for human/session recovery.

Use `--all-queries` to finish a reviewed query list after reaching the sample target, for example to add observed meme/template names that generic AI keywords miss. `--verify-top 150` selects the highest-view recent candidates plus all low-follower candidates with follower data returned in search. Before profile requests, exclude candidates without AI label/creator-text evidence and detected tutorials, because they cannot enter this AI ranking. Without the option, verify recent AI-evidenced candidates up to `--max-authors`. State this subset in the report; explicit source-video review is separate.

Count unique video IDs, not result cards, duplicated translations, accounts, or search-engine snippets. State total candidates, recent candidates, profile-verified videos and ranked videos separately. An unmet `--min-videos` target is unfinished work; do not claim 1,000 collected because 1,000 was configured. The CLI returns 3 for incomplete coverage/target, 2 for failures, 0 for its fulfilled completion condition; ranking remains a captured sample rather than a global TikTok leaderboard.

## Analysis and handoff

- Default window: rolling 30 days in UTC by publish time, excluding future-dated videos. Explain dates in the user's timezone when reporting.
- Account high interaction: latest snapshot per video, separate per-account collect/share averages, strict `metric > 2 × mean`. Missing metrics stay `NULL`, excluded from the corresponding average. Preserve zero. Report sample sizes and incomplete coverage.
- Search popularity: sort eligible recent, AI-evidenced videos by observed view count. A creator's AI hashtag or platform label is evidence of a claim, not independent visual verification. Exclude ordinary pet footage and unrelated tutorial/product content from a final content-only ranking after review. Keep “generated”, “remade/motion transfer”, “tutorial”, and “unverified” distinctions.
- Default low-follower viral thresholds: current followers `<=10,000`, views `>=100,000`, views/followers `>=10`; configurable. Missing/zero follower counts cannot qualify. Current followers do not establish follower counts at publication. This rule differs from account high interaction.
- Include capture timestamp, publish time, all available metrics, author identity, source video link, query provenance, AI evidence, ranking scope, missing fields and thresholds. Never fabricate inaccessible data or present third-party estimates as a primary verified ranking.
- Include **视频时长（秒）** in every video ranking and review table as a nullable number (`durationSeconds`). Keep the source unit explicit, convert only when required, and expose inclusive minimum/maximum duration filters through the shared schema controls. Missing or invalid duration stays null. When emphasizing the latest week, retain the publish timestamp and add a recent-seven-days filter based on an explicit collection cutoff.
- For requested `skillto-table` output, inspect its schema and existing MCP workspace, then create/reuse separate keyword, popular-video and low-follower tables through semantic tools. Use `short_video_info` for source-page playback links; do not pretend those links are direct video streams. Preserve missing metrics as null. Read back rows through MCP and give concrete table URLs. See [table mapping](references/table-output.md).

## Validation

Run `python scripts/test_crawler.py` for data semantics, six-stage retry escalation beyond six failures, visible waits, cancelled-wait resume, server Retry-After and manual verification beyond the old timeout. Browser fixtures can validate capture without live TikTok access; they do not replace a real collection acceptance run. Validate `SKILL.md` with skill-creator's `quick_validate.py` before packaging.
