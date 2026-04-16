# CHANGELOGS_0_3_0

Release date: 2026-04-16

## CDX Manager 0.3.0

CDX Manager 0.3.0 adds Python-native and standalone installation paths in addition to npm.

### Packaging

- Added `pyproject.toml` so the CLI can be installed with `pipx`, `pip`, or `uv tool`.
- Added the Python console entrypoint `cdx = "src.cli:cli_entry"`.
- Added `install.sh` for GitHub Release based installs into `~/.local/share/cdx-manager` with a symlink in `~/.local/bin`.
- Included `install.sh` and `pyproject.toml` in the npm package file list.
- Documented npm, pipx, uv, curl installer, and source installation paths.

### Validation

```bash
npm run lint
npm test
python3 -m venv /tmp/cdx-pyinstall
/tmp/cdx-pyinstall/bin/pip install --no-build-isolation .
/tmp/cdx-pyinstall/bin/cdx --version
npm --cache /tmp/cdx-npm-cache publish --dry-run
```

### Notes

- PyPI publication is now technically possible, but still requires PyPI credentials and an explicit publish step.
- The standalone installer defaults to the latest GitHub Release and supports `CDX_VERSION=vX.Y.Z` for pinned installs.
