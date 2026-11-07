# CDX Manager 0.26.8

Release date: 2026-11-07

## Improvements

- Resolve the conversation of a live Codex process (#125,
  `2150671b`). `cdx conversation <profile> --pid PID` and
  `--process-identity ID` read the exact conversation of a native Codex
  process, without falling back to workspace or recency matching.
- Add per-run provider arguments to `cdx run` (#120, `92620af`).
  `--extra-args 'ARGS'` is validated like the session setting and appended
  after the profile's arguments, without changing saved settings or
  interactive launches.

## Maintenance

- Record tray companion checksums for v0.26.7 (`bd53cb9`).
- Record release archive checksums for v0.26.7 (`145ec42`).
