# Changelog (`0.7.8 -> 0.8.0`)

Release date: 2026-06-08

## Release Governance

- Added a pre-publication release checksum gate that validates version alignment across `package.json`, `pyproject.toml`, `src/cli.py`, and `VERSION`.
- Publication workflows now require matching GitHub archive checksum metadata before npm or PyPI upload.
- Documented the release ordering for version bump, tag/archive checksum generation, checksum commit, and publication.

## Logics Workflow

- Versioned `LOGICS.md` as normal project guidance instead of treating it as an ignored local artifact.
- Added project documentation validation to ensure core Logics command families stay documented.
- Added `cdx view` as a thin shortcut for `logics-manager view`.
- Added `cdx view --json` diagnostics for companion availability, delegated command details, failure reason, and update suggestions.

## Maintainability

- Extracted the `cdx view` command domain into `src/cli_view.py` while keeping `src/cli_commands.py` as a compatibility facade for handler routing.

## Release Metadata

- Updated package metadata, CLI version output, README badge, pinned installer example, and release changelog to `v0.8.0`.

## Validation and Regression Evidence

- `python -m py_compile bin/cdx src/*.py test/test_*_py.py`
- `python -m unittest discover -s test -p 'test_*_py.py'`
- `npm pack --dry-run`
- `npm run lint`
- `npm test`
- `logics-manager lint --require-status`
- `logics-manager audit`
- `git diff --check`
- `node bin/cdx.js --version`
- `python3 bin/cdx --version`
- `python -m build`
- `python -m twine check dist/*`
