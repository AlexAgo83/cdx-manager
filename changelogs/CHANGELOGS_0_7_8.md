# Changelog (`0.7.6 -> 0.7.8`)

Release date: 2026-06-08

## Launch Guidance

- Added update guidance for `logics-manager` so `cdx` can surface a newer companion CLI version alongside the existing `cdx-manager` update notice.
- Added RTK launch preference handling so noisy assistant shell commands can be wrapped with `rtk` when the session setting asks for filtered command output.
- Extended provider launch metadata and health checks so companion tool hints appear without making `logics-manager` or RTK hard runtime dependencies.

## Coverage and Tests

- Added regression coverage for multi-tool update warnings, launch notice rendering, provider runtime launch metadata, and RTK preference handling.

## Release Metadata

- Updated package metadata, CLI version output, README badge, pinned installer example, and release changelog to `v0.7.8`.

## Validation and Regression Evidence

- `npm run lint`
- `npm test`
- `python -m unittest discover -s test -p 'test_*_py.py'`
- `python3 -m logics_manager lint --require-status`
- `git diff --check`
- `node bin/cdx.js --version`
- `python3 bin/cdx --version`
- `npm --cache /private/tmp/cdx-npm-cache pack --dry-run`
- `python -m build`
- `python -m twine check dist/*`
