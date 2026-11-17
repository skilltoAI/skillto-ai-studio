# TikTok cookie setup

Only use cookies from the login account authorized for the current task. Never paste a cookie into source, documentation, a report, or shell history. This skill cannot turn a syntactically valid cookie into a valid live session.

Resolution order:

1. Explicit `--cookies <path>`.
2. `TIKTOK_COOKIE_FILE`.
3. Windows: `%LOCALAPPDATA%/skillto.ai/secrets/tiktok-cookie.txt` (fallback: `~/AppData/Local/...`). macOS/Linux: `~/.config/skillto.ai/secrets/tiktok-cookie.txt`.

From your own logged-in TikTok browser, open developer tools > Network, navigate normally to TikTok, select a TikTok request, and copy its request Cookie header. Run `python <skill-root>/scripts/configure_cookie.py` in an interactive terminal and paste at the hidden prompt. The helper creates a private file (Windows current-user ACL; Unix mode 0600) and refuses replacement unless `--replace` is given. `--path` selects a different private destination. It accepts raw/Cookie-prefixed headers, TikTok-only Netscape cookies and JSON arrays/Playwright storage-state cookie lists. It ignores non-TikTok domains and expired cookies. Do not export unrelated browser state.

`python <skill-root>/scripts/configure_cookie.py --check` checks file format and expiry only, hiding all values. For an existing external protected file, pass `--cookies` rather than copying it into the skill. JSON cookie exports and browser profiles are secrets even when their extension is not `.txt`; keep them outside source control.

Normal capture runs in a background browser. CAPTCHA/login verification opens a visible manual window; `--challenge-wait 0` (default) waits until solved or cancelled, with status every 30 seconds. Updated cookies return in memory and the background page is rechecked. `--no-manual-challenge` disables the window; a positive `--challenge-wait` sets an explicit timeout. `--headed` shows the browser for the entire run. HTTP 429 waits at the longest backoff tier and honors a longer server Retry-After. Explicit access denial requires human/session recovery with pending work retained. See [pacing](pacing.md) for six escalating tiers, persistent retries and checkpoint resume. An empty response without explicit pagination exhaustion is incomplete, not proof of zero videos.
