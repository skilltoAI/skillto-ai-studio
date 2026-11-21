# Capture and storage

## Inputs

JSON is an array (or `{ "accounts": [...] }`):

```json
[{"platform":"tiktok","username":"example","url":"https://www.tiktok.com/@example","user_id":"123456789","sec_uid":"optional-secUid","name":"Display name"}]
```

`username` or a canonical HTTPS profile URL is required. `user_id`/`account_id` is an optional numeric platform ID, distinct from the mutable handle and `secUid`. CSV uses the same fields. TXT accepts a handle/profile URL per line, or `name,https://www.tiktok.com/@example`. No URL shorteners or non-TikTok navigation targets are accepted. An item's author must match the profile's stable numeric id and/or secUid, with every supplied identifier agreeing. The stored canonical author id always comes from the verified profile.

## Current web payloads

Observed candidates, not public API contracts:

| Source | Shape / binding |
| --- | --- |
| `#__UNIVERSAL_DATA_FOR_REHYDRATION__` | `__DEFAULT_SCOPE__["webapp.user-detail"].userInfo.user`, `.stats` / `.statsV2` |
| `#SIGI_STATE` | `UserModule.users`, `UserModule.stats`, `ItemModule` |
| `/api/user/detail/` | `userInfo.user` matched by `uniqueId`; compare configured stable IDs |
| `/api/post/item_list/` | `itemList` / `item_list`; query `secUid` must equal the verified profile's `secUid` |
| `/api/search/general/full/`, `/api/search/item/full/` | `data[].item` / `itemList`; retain stable author, keywords and capture time |

Common item fields: `id`, `desc`, `createTime` (Unix seconds), `author.id`, `author.secUid`, `author.uniqueId`, `video.cover`, `video.originCover`, `video.playAddr`, `video.duration`. `statsV2` overrides `stats`: `playCount`, `diggCount`, `commentCount`, `collectCount`, `shareCount`. Missing fields remain NULL. Count strings support commas and K/M/B. Do not map shares to reposts or favorites to likes. Hashtags come from text and `textExtra[].hashtagName`.

TikTok's official [Display API video object](https://developers.tiktok.com/docs/en/tiktok-api-v2-video-object) describes view/like/comment/share metrics; its [Research API](https://developers.tiktok.com/docs/en/research-api-specs-query-videos) also documents favorites. These official OAuth APIs require their own approval/scopes; a browser cookie is not an API access token. This implementation uses browser responses, not either official API. See [Playwright network monitoring](https://playwright.dev/python/docs/network) for the capture mechanism.

Attach listeners before navigation. Do not inspect recommendations/search payloads as profile posts. Initial hydration alone is partial. Account coverage is complete only when a bound post response explicitly returns `hasMore=false/0`; scroll limits, idle or old pinned posts do not prove full coverage. A nonzero application code alongside visible search cards must be recorded as a caveat; never ignore HTTP 401/403/429 or explicit login/challenge gates. The final search report always describes a sample.

## SQLite version 1

- `accounts`: stable `user_id` primary key, unique `sec_uid`, mutable username/name, current follower/video counts, avatar URL and last capture status/coverage.
- `videos`: global `video_id` primary key, account foreign key, stable author IDs, title/topics JSON, publish time, source URL, cover/media URLs, duration and update time. A CHECK requires account_id=author_user_id; writers additionally match secUid.
- `snapshots`: `(video_id,snapshot_date)` primary key; UTC capture timestamp and five nullable metrics. Repeated same-day observations replace that daily row. New days append; no historical counts are invented.
- `crawl_runs`: begin/end/status, requested/success/error counts, saved-item count and days.
- `account_runs`: each attempted account, time, bound identity if known, coverage, allowlisted error type and counts. Failed accounts without resolvable profile still have a record.

Read queries require both stored author IDs to match the account. Analysis uses the most recent snapshot per video. It excludes items outside `[now-days, now]` by publish time. CSV prefixes formula-leading strings; JSON preserves original titles and nulls. Public source/media URLs are retained as observed and may expire.
