# Changelog (`0.3.3 -> 0.3.4`)

Release date: 2026-04-16

## CDX Manager 0.3.4

CDX Manager 0.3.4 makes the CLI consumable by other applications through a structured JSON contract and rounds out the Windows release surface.

### JSON CLI API

- Added `cdx --json` to list known sessions as a machine-readable payload.
- Added `--json` support for session-management commands: `add`, `cp`, `ren`, `rmv`, `clean`, `login`, and `logout`.
- Added a shared success envelope for JSON responses with `ok`, `action`, `message`, and `warnings`.
- Added a shared stderr error envelope for JSON mode with machine-readable `code`, `message`, and `exit_code`.
- Documented the JSON contract in the README so editor plugins and desktop apps can integrate without scraping human-readable terminal output.

### Windows release hardening

- Added a native `install.ps1` installer for Windows.
- Documented supported Windows install paths and the optional transcript-capture fallback.
- Added targeted `win32` unit coverage for CLI startup, provider environment isolation, notifications, and session-store locking.
- Added a Windows CI smoke flow that installs the package and exercises core CLI commands with shimmed providers.

### Validation

```bash
npm run lint
npm test
npm_config_cache=/tmp/cdx-npm-cache npm pack --dry-run
python3 logics/skills/logics.py lint --require-status
```
