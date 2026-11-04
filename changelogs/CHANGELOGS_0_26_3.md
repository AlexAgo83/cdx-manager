# CDX Manager 0.26.3

Release date: 2026-11-04

## Improvements

- Make interactive session history findable and resumable (#110,
  `5abd37830095ee3519bd130ac6d80da143b29e27`). Filter `cdx history` by resolved
  working directory (`--cwd PATH`) and interactive launches (`--interactive`)
  before applying the result limit. Record launches immediately and update the
  same history row on exit so active sessions remain visible without duplicates.
- Support `cdx start <name>` through the named launch path, including tmux.
  Prefer exact Claude session IDs and unique project/time-scoped Codex transcript
  metadata; mark ambiguous recency matches as unverified. Recover clean, redacted
  first-user prompts past provider wrappers, reminders, tools and bare file paths.

## Maintenance

- Record tray companion checksums for v0.26.2
  (`54f201a2886f5293658f214e5725d60426dcfb28`).
- Record release archive checksums for v0.26.2
  (`3bc40eaada4b401e222bf599335b8b3d4dc80326`).
