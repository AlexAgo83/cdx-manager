# CDX Manager 0.9.8

## Highlights

- Hardened encrypted auth bundles so session names are no longer exposed in cleartext bundle metadata.
- Replaced deprecated tree removal handling with Python 3.12+ `onexc` support and a fallback for older supported Python versions.
- Added `pytest` coverage reporting and a `ruff` lint gate to local and CI validation.

## Changes

### Auth bundle privacy

Encrypted bundles now keep session names inside the encrypted payload instead of duplicating them in the cleartext wrapper.

Existing encrypted bundles that still contain cleartext `session_names` remain import-compatible.

### Runtime hardening

Profile tree deletion now uses `shutil.rmtree(..., onexc=...)` where available, avoiding the deprecated `onerror` path on Python 3.12+ while retaining compatibility with Python 3.9-3.11.

Auth bundle tests now skip cleanly when `cryptography` is unavailable in the active interpreter.

### CLI maintainability

Top-level command routing now uses an explicit dispatch table, with update notice suppression controlled by command metadata instead of an inline negative list.

### Tooling and CI

CI now installs the `dev` extra, runs `ruff check`, and executes the same `pytest` suite used locally with coverage reporting for `src/`.

The Python floor remains `>=3.9` for the 0.9.x line to avoid a compatibility break before a planned major support change.

## Validation

- `npm run release:validate`
- `npm run lint`
- `npm test`
- `logics-manager lint --require-status`
- `logics-manager audit`
- `git diff --check`
- `npm --cache /private/tmp/cdx-npm-cache pack --dry-run`
- `python -m build`
- `python -m twine check dist/*`
