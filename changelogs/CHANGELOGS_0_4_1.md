# Changelog (`0.4.0 -> 0.4.1`)

Release date: 2026-04-19

## CDX Manager 0.4.1

CDX Manager 0.4.1 fixes the Windows npm entry point so `cdx` no longer depends on `python3.exe` being present on PATH. It now ships a Node launcher that resolves a usable Python 3 interpreter cross-platform before invoking the existing Python CLI entry point.

### Windows npm launcher

- Replaced the npm-facing `bin.cdx` target with a Node launcher at `bin/cdx.js`.
- Added Python discovery that tries `py -3`, then `python`, then `python3` on Windows.
- Kept the existing Python script under `bin/cdx` as the primary CLI entry point.
- Added a clear error message when no compatible Python 3 interpreter is available.

### Documentation and packaging

- Updated the README with Windows Python prerequisites and the new launcher behavior.
- Added a shared portable Node wrapper for the npm test and lint scripts.
- Bumped the package versions for the npm and PyPI release workflows.

### Validation

```bash
npm run lint
npm test
node bin/cdx.js --version
```
