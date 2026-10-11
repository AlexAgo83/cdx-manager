# Release 0.21.2 preparation

Prepared locally on 2026-10-11. The checked-in release notes are `changelogs/CHANGELOGS_0_21_2.md`; the GitHub release title is the tag, `v0.21.2`.

## Scope

- Corrective release: tray companion instance lock restored after an OS temp purge.
- Release titles enforced to match their tag.
- Version metadata and README badge aligned to 0.21.2.

## Local receipts

- `npm test`: 1077 passed. `cargo test` (tray): 104 passed.
- `npm run lint`, `logics-manager lint --require-status`, and `git diff --check`: passed.
- Lock restoration checked on macOS with a local build: the `cdx-tray` runtime directory was deleted under a running companion and the pid file was back within 65 s; `cdx tray doctor` saw the companion again.
- `npm run release:validate`: version declarations agree; no 0.21.2 checksum entry yet, as expected before publication.
