# Background collection, persistent retries and human verification

The reference Douyin/Xiaohongshu collector also uses Playwright: a headless browser loads normal pages and observes XHR/fetch responses. TikTok uses the same method. Routine collection needs no visible browser or dashboard. A visible window is opened for human verification when needed.

## Six-stage retry policy

Keep collection serial. Default page/scroll wait is 3.5 seconds and the normal interval between units is 8 seconds. A unit is one search query, account, explicit video page or author verification. A transiently failing unit stays pending; wait, then retry that same unit. Do not advance as if it succeeded.

| Consecutive data anomalies | Random wait before retry |
| --- | --- |
| 1 | 1–5 seconds |
| 2 | 5–20 seconds |
| 3 | 20–60 seconds |
| 4 | 1–3 minutes |
| 5 | 3–10 minutes |
| 6 and every later failure | 10–60 minutes, newly drawn each time |

Navigation failures, missing/unparseable data and payload errors follow this policy. There is no default retry-count cutoff; the third and sixth failures do not stop the task. Each anomaly also doubles subsequent task/scroll intervals up to 8 times normal. A healthy result resets the consecutive anomaly count. Every three healthy results halves the extra slowdown. Usable duplicates and explicit pagination exhaustion are healthy; a search result with no new IDs can still be healthy. An empty response without exhaustion is an anomaly.

HTTP 429 uses the longest tier immediately. Wait at least the server's Retry-After if it is longer, even beyond 60 minutes. After that wait, recheck through ordinary navigation; do not replay APIs or rotate accounts/proxies. Explicit access denial requires human/session recovery; it is not an empty-data retry. Identity mismatch, invalid targets and private accounts are per-target unavailable results; proceed with other targets and disclose them. Never fabricate completion for inaccessible data.

## Visible waits and durable progress

Before sleeping, save the pending unit, error streak, slowdown, selected wait and UTC wake time. Search checkpoints also retain the deduplicated video pool, query attempts, successful author profiles and unavailable authors. Account/video checkpoints retain completed results. Reports and checkpoints contain public data and scheduling state, never cookies, authorization headers or browser storage state.

Print the anomaly reason, tier/count, duration and planned resumption time when backoff starts. Print remaining seconds, pending unit and progress at least every 30 seconds; announce resumption. Sleep in cancellable slices no longer than 10 seconds. When running the CLI for a user, relay meaningful wait/progress events to the conversation; a long wait is ongoing work, not completion. Human verification similarly emits status every 30 seconds.

`Ctrl+C` is explicit cancellation and exits with 130 while retaining the saved checkpoint. Restart the same command with `--resume`; honor any remaining cooldown rather than drawing a shorter one. `--checkpoint` and `--resume` work for search, crawl/update and explicit video capture. Use the same targets, data window/options, database and authorized session. Choose a separate checkpoint for a different task. Transient author failures are retried; a cached null profile does not count as completed verification.

The former `--cooldown-seconds`, `--cooldown-min`, `--max-cooldown` and `--anomaly-limit` options are removed. The six tiers are defined together in `scripts/pacing.py`; no legacy third-failure stop remains. Normal cadence remains configurable with `--account-delay` and `--wait-ms`.

## Human verification

On a visible CAPTCHA or login gate, retain pending work and open the configured browser channel in a visible window. Copy the authorized state in memory. The human completes verification; the collector never solves CAPTCHA. Transfer updated cookies back in memory, reload the original page once and check the result before resuming the same task. Normal runs omit `--headed`; that option shows the browser throughout a diagnostic run.

Default `--challenge-wait 0` waits until the human solves the gate or cancels/closes the window. There is no automatic 900-second timeout. A positive value explicitly sets a timeout. `--no-manual-challenge` explicitly disables the window. An unresolved gate, a closed manual window or explicit access denial is saved as requiring attention, with the pending unit retained for `--resume`. If the original context still has a device-bound challenge after manual completion, report the unresolved gate and preserve progress; do not claim success or silently switch sessions.

## Completion

Continue transient retries until each required unit produces usable data or explicit exhaustion. Keep advancing healthy work toward the user's requested count and finish the configured verification subset. If a healthy finite query list exhausts below the unique-video target, the run remains incomplete: expand/review the query plan and continue; repeating identical exhausted lists cannot increase the sample. Do not lower the target or count duplicate cards. Page scroll limits and usable partial account data remain honestly marked partial; they do not prove complete account history. Distinguish fulfilled targets, sampled/partial coverage and genuinely unavailable targets in the final handoff.

Offline tests mock long waits and human completion, so validation takes seconds and sends no TikTok traffic. These tests verify scheduling and state restoration; they do not establish current platform accessibility.
