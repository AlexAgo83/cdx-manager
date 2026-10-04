# Release 0.20.14 preparation

Prepared locally on 2026-10-04. Publication authorized subsequently; the following
receipts describe preparation, with final publication tracked by release evidence.

## Scope
- Seven new Codex/Claude model prices and model-specific cache-read discounts.
- Installed-CDX update instructions and reusable maintainer workflow in run_005.
- Version declarations and README badge aligned; CLI reports 0.20.14.
- Release notes: `changelogs/CHANGELOGS_0_20_14.md`.

## Local receipts
- `rtk npm test`: 1058 passed.
- `rtk npm run lint`: passed.
- `logics-manager lint --require-status`: passed.
- `git diff --check`: passed.
- `npm --cache /private/tmp/cdx-npm-cache pack --dry-run --json`: 172 files,
  including the updated pricing/stats modules and versioned changelog.
- `python3 -m build --outdir /tmp/cdx-0.20.14-dist`: sdist and wheel built.
- `python3 -m twine check /tmp/cdx-0.20.14-dist/*`: both passed. Wheel metadata
  is 0.20.14 and includes the updated pricing and commands modules.
- `npm run release:validate`: declarations consistent; explicitly reports no
  checksum entry for the unpublished version. This is not checksum proof.

## Remaining release gates
- Global Logics audit blocker resolved: run_004 had recorded verification but
  remained Draft. Activated it after reviewing command scope and corrected its
  Codex history location guidance. Original cleanup date retained; no cleanup run.
- Commit reviewed work, push and verify CI for the exact release commit.
- Push v0.20.14 and generate archive checksum metadata; verify strict checksum
  validation and the complete tray/checksum release assets.
- Publish GitHub/npm/PyPI and record fresh version-specific evidence. Current
  `logics-manager release validate 0.20.14` is expected to remain blocked by the
  dirty checkout and pending publication gates; do not claim release-ready.
