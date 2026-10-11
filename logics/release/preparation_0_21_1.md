# Release 0.21.1 preparation

Prepared locally on 2026-10-11. The checked-in release notes are `changelogs/CHANGELOGS_0_21_1.md`; the intended GitHub release title is **CDX Manager 0.21.1** with tag `v0.21.1`.

## Scope

- Corrective release: macOS tray memory leak and update-check stalls on degraded networks.
- Version metadata and README badge aligned to 0.21.1.

## Local receipts

- `npm test`: 1077 passed.
- `npm run lint`, `logics-manager lint --require-status`, and `git diff --check`: passed.
- `npm run release:validate`: version declarations agree; no 0.21.1 checksum entry yet, as expected before publication.

## Remaining release gates

- Push and verify CI for the release commit, then tag `v0.21.1` and publish the GitHub release with the checked-in changelog.
