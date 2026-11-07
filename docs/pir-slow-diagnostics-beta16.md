# Beta16 — PIR slow diagnostics design

Status: implementation plan; no runtime behavior changed by this document.

## Classification

Classify a slow PIR zone read using `read_ms` (sum of zone batch read durations), not `interval_ms` or `resync_wait_ms`:

- `read_ms < 1000`: no slow-read record.
- `1000 <= read_ms < 1500`: DEBUG.
- `1500 <= read_ms < 2000`: INFO.
- `read_ms >= 2000`: WARNING.

Keep the existing separate delayed-poll diagnostics for resynchronization/interval anomalies. Do not conflate slow zone reads with an EVENT/POLL resync wait. Preserve timing breakdowns (`interval_ms`, `lock_wait_ms`, `read_ms`, `resync_wait_ms`, `batches`) for troubleshooting.

## Repeated reads

- A repeated-slow-read incident is at least three slow reads in a rolling 60-second window.
- Emit a distinct WARNING, with the occurrence count and maximum `read_ms` in that window.
- Rate-limit repeated-slow-read WARNING messages to one per ten minutes, without suppressing individual >=2000 ms WARNING messages.
- Use monotonic time for rate limiting, and timestamps for display.
- Do not issue a new repeated WARNING on every poll after the threshold is reached.

## Diagnostic sensor

- Add a diagnostic sensor, disabled by default, analogous to `Last FlexC event ID`.
- State: count of PIR slow reads (`read_ms >= 1000`) in the trailing 60 minutes.
- Attributes: maximum `read_ms` in that window and a bounded list of timestamped slow reads, newest first, with read duration and relevant timings/batches.
- Keep a bounded, expiring in-memory history; no persistent unbounded log and no extra network polling.
- Ensure expiration updates the sensor even if no new slow reads arrive. Document that the history resets on restart.

## Card

- Under the System tab, immediately after FlexC event history and before RF, add a PIR diagnostics collapsible section, collapsed by default.
- When enabled, show the count in the collapsed label and the timestamped slow-read list when expanded, newest first.
- When enabled with zero events, show `0 lectures lentes (1 h)` and a clear empty-state message.
- When disabled, show an activation instruction instead of a misleading zero.
- Distinguish disabled from unavailable/unknown states.
- Keep the card's existing localization and responsive styles.

## Validation before release

- Python tests: exact threshold boundaries; rolling 60s and 60min expiry; repeated warning and ten-minute cooldown; no additional polling; restart/empty history.
- JavaScript tests: disabled, zero, populated, unavailable, chronological display and collapsed-by-default behavior.
- Run full CI and review the beta16 changelog and Signed release dry run before publishing.
