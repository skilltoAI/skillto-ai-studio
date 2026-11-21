# Motion local operations

Resolve `scripts/motion_cli.py` from this skill. The service is the existing Studio loopback service, default `http://127.0.0.1:8880`; `--url` selects another explicitly configured local endpoint. CLI fetches the same-origin write token; no separate credentials are needed. Only new Motion operations are added; table MCP operations do not mutate this library.

```sh
python scripts/motion_cli.py catalog
python scripts/motion_cli.py seed
python scripts/motion_cli.py doctor
python scripts/motion_cli.py render --file /absolute/path/request.json
```

Use an argument file rather than shell-escaped multiline JSON. The action is the CLI positional argument. Arguments:

| Action | JSON fields |
| --- | --- |
| add | title, sourceUrl; optional category, aspect, source, previewUrl, downloadUrl |
| update | id; optional title, category, favorite, rating (0.5–5, step 0.5, or null), tagIds (complete selection) |
| tag | operation: save/delete; id for rename/delete; name for create/rename |
| download | id; uses recorded public downloadUrl |
| import | id, path: absolute .motion file path |
| render | id, keyword (1–8 Chinese characters), text (1–42 characters, up to two lines), optional title; or parameters: complete package input JSON |
| cancel / retry | id: task ID; retry creates a new task and retains previous outputs |
| remove | id: library item; preserves original package and production files |

Full `parameters` take precedence over the B1 text shortcut. Use the imported package's `params.schema.json`, `guide.json`, `CREATION.md` and selected scene declarations; do not invent media roles, timings, licensing or output aspect support. Paths in supplied media bindings must be real host files. Renderer validates input before preparation. For text-only B1 the actual native sequence is 8 seconds, landscape 1920×1080/60fps, with native action sounds and no invented voice or soundtrack.

## Storage and jobs

`SKILLTO_TABLE_ROOT/motions/` contains `library.sqlite3` (records and append-only history), `packages/<sha>.motion`, `runners/<sha>/`, `instances/<jobId>/`, and bounded preview cache `media/`. Runtime paths and dependencies live in `runtime.local.json` and `environment/`, never in distributed skill files. Each instance retains `input.json`, `plan.json`, `scene/`, `preview.png`, `task.log` and `video-with-audio.mp4` when successful.

Tasks progress queued → running → succeeded/failed; cancellation progresses cancelling → cancelled. Downloads and renders use a serial background queue (maximum ten active jobs). The HTTP thread stays available. Cancelling terminates the owned process tree. Retry never overwrites old outputs. Restart only an idle service; interrupted jobs are marked failed on startup and can be retried.

The public reader supports ZIP bounds: 384 MiB archive, 5000 entries, 600 MiB expanded, 150 MiB per file, and max 200× compression for files over 10 MiB. It rejects absolute/traversal/aliased paths, symlinks, special entries, conflicting names and inconsistent integrity membership. Unknown optional manifest metadata is retained. Run eligibility requires the pinned known archive hash, and original/extracted content is rechecked before execution.

## Setup and dependencies

Use `scripts/setup_motion.py --ffmpeg-directory <existing bin> --chrome <existing browser exe>` with Python 3.11+. It creates an isolated environment below the runtime root and installs only the template's Python requirements. Node 22+ and npm are required; the pinned package lock drives `npm ci --ignore-scripts` on first render. Record actual installed versions in the runtime environment lock. If a dependency is missing, report it or install the declared missing dependency within the user's authorization; do not silently switch engines.

The first verified Windows renderer uses a full FFmpeg build with colorspace, scale and sidedata filters, libx264 and AAC. Trimmed application-bundled FFmpeg builds may lack required filters. The template's own `playwright-core` is used as the frame renderer, not for automating the user's browser session.

## HTTP and UI

GET `/api/motions/catalog`, `/api/motions/doctor`, `/api/motions/session`; POST `/api/motions/action` takes the semantic action JSON. POST `/api/motions/upload?id=<itemId>` streams a bounded .motion body. Mutations require the transient `X-Motion-Token` and matching Origin when present. No CORS is enabled. Registered previews get cached poster frames through `/api/motions/poster/<id>`; a failed cover falls back to the preview button. Range-capable media routes serve only registered template previews or fixed output names belonging to real jobs; arbitrary local paths cannot be served.

Default sort: source run count descending, publication date descending, stable ID. Nulls last; 0 is real data. Source adapters currently have no verified run-count feed, so imported reference records show null. Ratings never fill that field. Filter AND across dimensions; tags all/any selectable. Selection clears on filter navigation. Clipboard is one path/URL per line in current result order; skips unavailable values, with count feedback. Both buttons have accessible labels and tooltips even though visible UI uses icons only.

Accept after actual local preview/render, media probing and visual/audio inspection; verify tags, filters, source-stat nulls, score persistence, clipboard differences, failure/retry/cancel, broken local paths, narrow screens and original module navigation. Keep runtime acceptance artifacts outside Git.

## Browsing and preview media

`view` with `id` records the first detail opening (`viewed: true`, `viewedAt`). Hover, sync and imports do not count. Unscored viewed items receive rating 1 and `ratingSource: view-default`; numeric `update.rating` is manual and never overwritten by views. Clearing a viewed score returns to default 1. Legacy records without explicit browsing evidence remain unviewed. Source run counts are independent. The upper-right filter supports all/viewed/unviewed and is retained in the URL.

Allowlisted preview MP4s are cached atomically with a 512 MiB bound (Mac Desktop is about 202 MiB); cached playback supports byte ranges. The initial uncached preview waits for the download. Package download limits and source allowlists are unchanged.

## Demo compression during intake/sync

`sync_index` and `ingest` return `mediaJob` after committing metadata (dryRun does not enqueue media). Poll catalog for completion and inspect `mediaResults`; retry failed jobs. `mediaError` means metadata succeeded but enqueue failed. `prepare_previews` with optional `ids` processes an existing selection; omitted ids means all remote demo entries. This does not modify .motion packages, source URLs or manual ratings.

Videos >40,000,000 bytes are temporary inputs only: transcode HEVC/hvc1 720p, preserve aspect, no crop/upscale; AAC audio and MP4 faststart. Large sources and partial outputs are cleaned on success/failure/cancellation. Only validated derivatives + provenance remain. <=40 MB videos stay unchanged and are lazily cached on playback. Background tasks check sizes with HEAD first. The 512 MiB acquisition bound remains.

Official `github.com/motiontemplates/all/releases/download/...` demo assets are supported. Public signed redirects are accepted only from this official release path to `release-assets.githubusercontent.com`; direct signed URLs and other GitHub repositories remain rejected. Signed redirect URLs are transient and must not be stored or logged.

On a host with a verified NVIDIA HEVC encoder, runtime.local.json may set `previewEncoder: hevc_nvenc` after a real encoder test. Default remains libx265; both produce validated HEVC/hvc1 720p. No codec substitution occurs if hardware encoding fails; job diagnostics and retry remain available.

## Rating range filters

The toolbar 评分 control applies inclusive ratingMin/ratingMax at half-star steps, with either bound optional. Sources: all, manual (including legacy numeric ratings), view-default, or unrated. Unrated clears/disables bounds; null never matches a numeric range. The URL retains motion_ratingMin, motion_ratingMax, motion_ratingKind alongside existing filters. Clearing this control preserves unrelated filters; global reset clears all.
