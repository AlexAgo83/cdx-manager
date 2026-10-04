# Technical reference

## Technical Overview

- Python 3.9+.
- Environment isolation per session:
  - Codex sessions override `CODEX_HOME` to a dedicated profile directory.
  - Claude sessions override `HOME` to a dedicated profile directory and disable Claude Code commit co-author attribution by default.
  - On macOS, Claude credentials use a profile-specific keychain entry. Quota refresh reads that entry before legacy credential files; `cdx cp` and `cdx ren` transfer only the profile's entry, never the system keychain directory. Rename refuses existing destination entries and reports any old-entry cleanup failure after the new session becomes usable; `cdx rm` deletes the profile's entry with the profile.
  - Antigravity sessions launch `agy` with a dedicated `HOME` for file-based settings; Google account credentials may still be stored in the OS keyring by Antigravity itself.
  - Ollama sessions use the local Ollama server and launch `ollama run <model>`; set a model with `cdx set <name> --model <model>`.
  - New Codex sessions seed their auth home from your existing global `~/.codex/auth.json` when available, so an already logged-in Codex CLI can be reused without giving up per-session isolation afterward.
- Persistence:
  - Session registry at `~/.cdx/sessions.json` (versioned JSON store).
  - Per-session state at `~/.cdx/state/<name>.json`.
  - Per-workspace shared context at `~/.cdx/contexts/<workspace-hash>/context.md`.
  - Auth and provider data under `~/.cdx/profiles/<name>/`.
  - All paths are URL-encoded to support arbitrary session names.
- Status resolution pipeline:
  - Primary source: recorded status fields on the session record.
  - Codex live source: `codex app-server` JSON-RPC `account/rateLimits/read`, normalized into 5-hour, weekly, reset, credit, and plan fields.
  - Fallback: `status-source` scans provider JSONL history files and terminal log transcripts, strips ANSI/OSC sequences, and extracts `usage%`, `5h remaining%`, and `week remaining%` via pattern matching.
- Status latency controls: use `cdx status --cached` to skip live probes, `cdx status --timeout SECONDS` for one command, or `CDX_STATUS_TIMEOUT_SECONDS` to lower the default Codex live-probe timeout.
- Claude status refreshes are cached briefly by default; pass `--refresh` to force a live rate-limit probe.
- On Linux, transcript capture uses the `util-linux` `script -c` command form.
- If `script` is unavailable, Codex launch falls back to running without transcript capture.
- On Windows, transcript capture is optional. If no compatible `script` wrapper is installed, Codex still launches normally without transcript capture.
- Auth probe: synchronous subprocess call to `codex login status` or `claude auth status` before any interactive launch.
- Signal forwarding: `SIGINT`, `SIGTERM`, and `SIGHUP` are forwarded to the child process and produce clean exit codes.
- Test stack: `pytest`, `pytest-cov`, and `ruff` via the documented `dev` dependency extra.

## Project Structure

```text
bin/
  cdx.js                # Node launcher used by npm
  python-runner.js      # Shared Python resolver and process wrapper
  cdx                   # Python entrypoint invoked by the launcher

src/
  cli.py                # Top-level command router
  cli_commands.py       # Command handlers and argument handling
  cli_render.py         # Terminal formatting, tables, colors, and errors
  backup_bundle.py      # Portable session bundle encoding/decoding + auth encryption
  status_view.py        # Status table/detail rendering and priority ranking
  provider_runtime.py   # Provider launch/auth commands, transcripts, signals
  claude_refresh.py     # Claude usage refresh orchestration
  session_service.py    # Session lifecycle: create, copy, rename, launch, remove, status
                        # resolution, auth state management
  session_store.py      # JSON persistence layer: sessions.json + per-session
                        # state files
  status_source.py      # Status artifact discovery: scans JSONL history files
                        # and terminal log transcripts, strips ANSI sequences,
                        # extracts usage metrics via pattern matching
  config.py             # CDX_HOME resolution (env override or ~/.cdx)
  errors.py             # CdxError with optional exit code
  __init__.py           # Public Python exports

test/
  test_cli_py.py            # CLI command dispatch tests
  test_session_service_py.py  # Session service unit tests
```

## Data Layout

All session data lives under `CDX_HOME` (default: `~/.cdx/`):

```text
~/.cdx/
  sessions.json             # Session registry (versioned, all sessions)
  state/
    <encoded-name>.json     # Per-session rehydration state
    launch_history.jsonl    # Append-only launch history
  contexts/
    <workspace-hash>/context.md     # Current-workspace shared context / memory
    global/context.md               # Global cdx memory
    projects/<encoded-name>/context.md  # Named project memory from cdx memory --project NAME
  profiles/
    <encoded-name>/         # Codex session: CODEX_HOME points here
      log/
        cdx-session.log     # Terminal transcript (written by script(1))
    <encoded-name>/
      claude-home/          # Claude session: HOME points here
        log/
          cdx-session.log
```

Session names are URL-encoded when used as directory or file names. CLI command names such as `add`, `disk`, `status`, and `login` are reserved and cannot be used as new session names.

`cdx memory` is the user-facing interface for explicit memory. `--project NAME` uses a stable free-form project name; `--project /path/to/repo` resolves to the same workspace-hash memory that repo would use as the current workspace. `append` adds the text as-is with a clean newline boundary; it does not add dates or headings. `list` reports global memory, named project memories, and the current workspace memory when present; it does not scan your filesystem for repos.

Provider-private memory files, such as Codex SQLite memory databases or Claude Code project memory files, are not edited by `cdx memory`.
