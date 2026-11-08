# CDX Manager 0.26.9

Release date: 2026-11-08

## Fixes

- Resolve the conversation of a live interactive Codex process from the
  rollout file it holds open (#126, `abb19e0`). `cdx conversation <profile>
  --pid PID` no longer answers `native_conversation_identity_unavailable`
  for an interactive Codex session whose native process writes an exact
  rollout; it still refuses workspace or recency guesses.

## Maintenance

- Record tray companion checksums for v0.26.8 (`e04fae8`).
- Record release archive checksums for v0.26.8 (`f41f2b3`).
