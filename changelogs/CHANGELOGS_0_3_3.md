# CHANGELOGS_0_3_3

Release date: 2026-04-16

## CDX Manager 0.3.3

CDX Manager 0.3.3 adds Windows compatibility across the full codebase.

### Windows support

- **Session store locking**: replaced `fcntl.flock` (Unix-only) with `msvcrt.locking` on Windows, with `seek(0)` to ensure consistent byte-range locking.
- **Signal handling**: guarded `signal.SIGHUP` references behind `hasattr` checks — `SIGHUP` does not exist on Windows.
- **Profile isolation**: added `_home_env_overrides()` helper that sets `USERPROFILE`, `HOMEDRIVE`, and `HOMEPATH` in addition to `HOME` when launching the `claude` CLI on Windows, so Node.js `os.homedir()` resolves to the correct session profile.
- **Desktop notifications**: `cdx notify` now sends a notification via PowerShell `System.Windows.Forms.MessageBox` on Windows (falls back silently if PowerShell is unavailable).
- **ANSI colors**: `cli_entry` enables VT processing via `ctypes.windll.kernel32.SetConsoleMode` on Windows so color output works in terminals that support it.
- **Console encoding**: `cli_entry` reconfigures `stdout`/`stderr` to UTF-8 on Windows to prevent `UnicodeEncodeError` on non-ASCII session names.

### Maintenance

- Expanded `.gitignore` with standard Python build artifacts (`__pycache__/`, `*.egg-info/`, `dist/`, `build/`), virtual environments, coverage output, and OS-specific files (`.DS_Store`, `Thumbs.db`, `desktop.ini`).

### Validation

```bash
npm run lint
npm test
```
