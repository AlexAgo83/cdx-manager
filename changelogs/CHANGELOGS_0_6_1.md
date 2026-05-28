# Changelog (`0.6.0 -> 0.6.1`)

Release date: 2026-05-28

## Handoff Reliability

- Fixed `cdx handoff <source> <target>` when a source session has no `cdx-session*.log` launch transcript.
- Added fallback discovery for native provider histories, including Claude project JSONL files under the isolated session home.
- Converted JSONL message records into readable role-prefixed handoff context instead of requiring raw terminal logs.

## Linux Transcript Capture

- Fixed default transcript capture on Linux and Arch Linux by using the `util-linux` `script -q -F -c "<command>" <transcript>` form.
- Kept the existing BSD/macOS `script` invocation unchanged.
- Preserved custom `CDX_SCRIPT_ARGS` behavior for users who explicitly configure their wrapper.

## Release Metadata and Documentation

- Updated package metadata, CLI version output, README badge, and pinned installer example to `v0.6.1`.
- Documented the Linux-specific transcript capture behavior in the README.

## Validation and Regression Coverage

- Added regression coverage for Claude-to-Claude handoff from native `.claude/projects/*.jsonl` history when no launch log exists.
- Added runtime coverage for the Linux `script` invocation shape.

## Validation and Regression Evidence

- `npm run lint`
- `npm test`
