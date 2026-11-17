# Report-table mapping

Use an installed `skillto-table` or `skillto-ai-studio-table` and read its SKILL.md, schema and target-selection instructions. Discover the existing workspace via its semantic MCP tool, then create a research project with three tables:

- **Keyword expansion**: seed, animal, language, proposed query, animal aliases, AI/remake modifiers, query class (proposal/observed trend), evidence URL, ambiguity note.
- **Recent popular videos**: rank, TikTok video id (business identity), title, creator, stable author id, followers, video duration in seconds, publish time, capture time, views, likes, comments, collects, shares, query hits, AI evidence, production type, verification status, coverage and source URL.
- **Low-follower viral videos**: same fields plus views/followers and exact thresholds/reason. Use only qualified rows; missing follower data must not be shown as zero. An empty table means no *verified* matches yet, not proof no such content exists.

The CLI's search report has `expansion`, `query_runs`, `searched_unique`, `recent_candidates`, `videos`, `top_videos`, `low_follower_viral`, `thresholds`, timestamps and limitations. Create a separate run/status table when needed to preserve incomplete acceptance rather than filling a results table with fabricated placeholder videos.

Declare `durationSeconds` with label **视频时长（秒）** and type `number`, placed among the default visible columns. The parsed TikTok `duration` is in seconds; do not divide it by 1,000. Preserve absent/nonpositive duration as null. The table's shared schema controls must create decimal minimum/maximum duration inputs automatically; test an inclusive interval and reset through MCP and the rendered page. For a requested recent-week emphasis, merge useful week candidates with the month selection, retain an explicit cutoff, and declare a boolean **最近7天** filter instead of silently discarding older month results.

For video rows, preserve the original source link and use a `short_video_info` field:

```json
[{"id":"123456789","title":"Example","publishedAt":"2026-10-01T08:00:00Z","playCount":null,"likeCount":null,"collectCount":null,"shareCount":null,"commentCount":null,"coverUrl":"https://example.com/cover.jpg","videoUrl":"https://www.tiktok.com/@example/video/123456789"}]
```

`videoUrl` opens the source page. Do not add it as an MP4 in `media`, which would create a broken embedded player. Image/video previews need actual media URLs, and expiring media need refreshed references. Never add cookies or session-bearing request URLs to a table.

Create/update schema and rows through semantic MCP. Use TikTok video id to query before inserting, so reruns update rather than duplicate a row. Tags are local to each table; preserve existing tags, reviews and history. Re-query after writes and hand off the specific table URL on the selected local or remote service. Do not silently copy local data to AMD-PAD or claim MCP is active when only a static export was created.
