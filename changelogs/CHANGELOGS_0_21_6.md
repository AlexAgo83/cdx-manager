# CDX Manager 0.21.6

## Security

- **Windows toasts.** PowerShell also ends a single-quoted string on the typographic quotes ‘ ’ ‚ ‛, so those are now escaped too, in cdx and in the tray. A crafted folder name or response preview could run code. French text such as "l’agent" no longer drops the toast (#23).
- **Tray over WSL.** The tray no longer passes its commands through the WSL shell, which expanded `$(...)` and split arguments containing spaces. It also finds the user's own `cdx` instead of a stale system-wide one (#23).
- **`cdx set <name> --scrub-env on`** launches Claude with `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`. The Bash commands, hooks and MCP servers the agent starts then no longer receive credentials, including the setup-token. It is off by default; `docs/operations.md` explains the trade-off (#26).
- **Backup bundles that include auth** use a stronger key derivation (scrypt N=2^17, or PBKDF2 at 600k iterations) and record its cost. Older bundles still import, and a crafted cost is refused (#25).
- **Claude profile creation** no longer replaces an unparseable or symlinked `settings.json`, and keeps its permissions (#23).
- **PyPI** releases are published with Trusted Publishing, without a stored API token (#27).

## Fixes

- **Windows:**
  - `cdx.cmd` now returns the real exit code; it always returned 0;
  - `cdx ready` schedules its task on any Windows language, where `schtasks` refused the date on non-US systems;
  - provider output is read as UTF-8;
  - `cdx -v` and `--help` work without a home directory;
  - the check after `cdx update` no longer prints "Could not determine home directory" (#22, #23).
- **`cdx run`** stops the provider when it receives SIGTERM or SIGHUP (a `kill`, a `systemctl stop` or a closed SSH session), not only on Ctrl+C (#24).
- **No more lost writes when two commands overlap:**
  - tray events published while another is being acknowledged are kept;
  - `cdx context set` and `clear` no longer race with an append (#24).
- **`cdx set`:**
  - the usage line, help and docs list every flag;
  - a bad on/off value names the flag, for example "Unsupported notify value: maybe (on|off)" (#25).
- **`cdx schema --json`** publishes every run error code and warning code. `cdx run` sets its error codes at the source instead of reading the message text (#25).

## Housekeeping

- CI also tests Python 3.9, the minimum version declared in pyproject.
- The tray builds with `cargo --locked`.
- The test suite no longer touches the developer's real macOS keychain (#24, #25).
