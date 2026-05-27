# Changelog (`0.5.7 -> 0.6.0`)

Release date: 2026-05-28

## Major Highlights

- Added launch history workflows for reviewing, summarizing, and relaunching assistant sessions.
- Improved `cdx status` guidance with reset-week countdowns, active-session marking, cleaner blocking quota labels, and periodic update notices.
- Added shortcut commands that reduce routine assistant switching and waiting friction.

## Launch History and Relaunch

- Added `cdx history` to inspect recent assistant launches with provider, result, duration, working directory, launch settings, and transcript path.
- Added `cdx history --summary` to aggregate assistant time by session.
- Added period filters for history summaries with `--since`, `--from`, and `--to`.
- Added `cdx last` to relaunch the most recent existing session from launch history.
- Skips removed sessions when resolving the last launch target.

## Status and Availability

- Added reset-week countdowns to status output.
- Hid healthy blocking quota labels so status tables stay focused on actionable quota limits.
- Marked the active launched session in status and list output.
- Added `cdx ready` as a shortcut for scheduling the next assistant reset notification.
- Added update notices to `cdx status`, matching the existing periodic update check behavior.
- Changed visual update notices to show `Run: cdx update` instead of a release URL.

## CLI Ergonomics

- Curated the main screen next-actions list around the commands users are most likely to run next.
- Kept release URLs in JSON warning payloads for integrations while making text output directly actionable.
- Added `cdx last [--json]` to help output and README command documentation.

## Release Metadata and Documentation

- Updated package metadata, CLI version output, README badge, and pinned installer example to `v0.6.0`.
- Documented `cdx last` and the action-oriented update notices in the README.

## Validation and Regression Coverage

- Added regression coverage for launch history, assistant-time summaries, period filters, active session indicators, `cdx ready`, `cdx last`, and update notices in `cdx status`.
- Added coverage to ensure visual update notices show `Run: cdx update` without leaking the release URL.

## Validation and Regression Evidence

- `npm run lint`
- `npm test`
