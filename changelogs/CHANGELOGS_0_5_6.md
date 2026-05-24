# Changelog (`0.5.5 -> 0.5.6`)

Release date: 2026-05-24

## Major Highlights

- Reduced noisy `cdx status` progress output by respecting fresh cached status rows.
- Stopped probing disabled sessions during status resolution and hid stale quota metrics for disabled rows.
- Refined `cdx notify --next-ready` so it waits for the next blocked account reset instead of notifying for an account that is already usable.

## Status Output

- Added status-row cache handling so recently resolved rows do not print redundant `Checking ...` progress lines.
- Kept Claude status cache behavior aligned with the Claude refresh TTL, avoiding unnecessary Claude checks while cached usage is still fresh.
- Treated disabled sessions as display-only in `cdx status`; disabled sessions remain visible but are not refreshed or re-read from status artifacts.
- Rendered disabled-session quota columns as `-` for `OK`, `5H`, `WEEK`, `BLOCK`, `CR`, `RESET 5H`, and `RESET WEEK`.
- Preserved the stored last status internally so re-enabled sessions can resume normal status behavior.

## Notifications

- Added `--refresh` support to `cdx notify` so notification checks can force status refreshes when requested.
- Added text-mode progress output for notification checks while keeping `--json` output clean.
- Made `cdx notify --next-ready` ignore disabled sessions.
- Made `cdx notify --next-ready` ignore sessions that are already usable and instead target the next currently blocked session with a known reset.
- Returned `No upcoming session reset available` when there is no blocked session with a reset to wait for.

## Documentation

- Updated package metadata, CLI version output, README badge, and pinned installer example to `v0.5.6`.
- Documented `--refresh` for `cdx notify` command examples.

## Validation and Regression Coverage

- Added regression coverage for cached Codex status rows suppressing redundant checking progress.
- Added regression coverage for Claude cache TTL behavior.
- Added regression coverage for disabled sessions skipping refresh and hiding public status metrics.
- Added regression coverage for `notify --next-ready` ignoring already-available and disabled sessions.

## Validation and Regression Evidence

- `npm run test:py`
- `./bin/cdx status`
