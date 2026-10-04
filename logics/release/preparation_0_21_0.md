# Release 0.21.0 preparation

Prepared locally on 2026-10-04. The checked-in release notes are `changelogs/CHANGELOGS_0_21_0.md`; the intended GitHub release title is **CDX Manager 0.21.0** with tag `v0.21.0`.

## Scope

- Recovery and persistence hardening across force imports, concurrent appends, failover accounting, interactive usage, model pricing, and exact handoff source selection.
- Version metadata and README badge aligned to 0.21.0.
- Corrected the existing v0.20.14 GitHub release title to **CDX Manager 0.20.14** so the release list follows the established naming pattern.

## Local receipts

- `rtk npm test`: 1076 passed.
- `rtk npm run lint`, `logics-manager lint --require-status`, `logics-manager audit --group-by-doc`, and `git diff --check`: passed.
- `npm --cache /private/tmp/cdx-npm-cache pack --dry-run --json`: 173 files, including `VERSION` and the 0.21.0 changelog.
- `python3 -m build --outdir /tmp/cdx-0.21.0-dist`: sdist and wheel built; `python3 -m twine check` passed for both.
- `npm run release:validate`: version declarations agree. It reports no 0.21.0 checksum entry yet, as expected before publication; this is not checksum proof.
- The v0.20.14 GitHub release title was corrected and verified as **CDX Manager 0.20.14**.

## Remaining release gates

- Commit, push, and verify CI for the release commit.
- Create tag `v0.21.0`, publish GitHub release with the checked-in changelog and the intended title, then generate and verify archive/tray checksums.
- Publish npm and PyPI packages and record fresh version-specific evidence. Do not claim release readiness from the previous version's evidence.
