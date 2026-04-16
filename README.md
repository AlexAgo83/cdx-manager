# CDX Manager

**Run multiple Codex and Claude sessions from one terminal. Switch between accounts instantly.**

If you use AI coding tools at scale ; multiple accounts, multiple providers : you know the friction: re-authenticating, losing context, juggling environment variables. `cdx` removes all of that.

One command to launch any session. Zero auth juggling.

[![License](https://img.shields.io/badge/license-MIT-4C8BF5)](LICENSE) ![Version](https://img.shields.io/badge/version-v0.3.4-4C8BF5) ![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)

---

## Table of Contents

- [What it does](#what-it-does)
- [Technical Overview](#technical-overview)
- [Getting Started](#getting-started)
- [All Commands](#all-commands)
- [JSON Output](#json-output)
- [Available Scripts](#available-scripts)
- [Windows Support](#windows-support)
- [Project Structure](#project-structure)
- [Data Layout](#data-layout)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## What it does

- **Multiple accounts, one tool.** Register as many Codex or Claude sessions as you need. Each one gets its own isolated auth environment — no cross-contamination between accounts.
- **Instant launch.** `cdx work` opens your "work" session. `cdx personal` opens another. No config files to edit mid-flow.
- **Auth guardrails.** `cdx` checks authentication before launching. If a session is not logged in, it tells you exactly what to run — no silent failures.
- **Usage at a glance.** `cdx status` shows token usage, 5-hour window quota, weekly quota, and last-updated timestamps for every session in one aligned table.
- **Passive status resolution.** If a session has no recorded status, `cdx` reads it directly from the provider's session logs and JSONL history — no manual sync required.
- **Session transcript capture.** Every launch is recorded to a local log file via `script`, giving you a full terminal transcript for each session.
- **Clean removal.** `cdx rmv` wipes a session and its entire auth directory. No orphaned files, no stale credentials.

---

## Technical Overview

- Python 3.9+, zero runtime dependencies.
- Environment isolation per session:
  - Codex sessions override `CODEX_HOME` to a dedicated profile directory.
  - Claude sessions override `HOME` to a dedicated profile directory.
- Persistence:
  - Session registry at `~/.cdx/sessions.json` (versioned JSON store).
  - Per-session state at `~/.cdx/state/<name>.json`.
  - Auth and provider data under `~/.cdx/profiles/<name>/`.
  - All paths are URL-encoded to support arbitrary session names.
- Status resolution pipeline:
  - Primary source: recorded status fields on the session record.
  - Fallback: `status-source` scans provider JSONL history files and terminal log transcripts, strips ANSI/OSC sequences, and extracts `usage%`, `5h remaining%`, and `week remaining%` via pattern matching.
- Claude status refreshes are cached briefly by default; pass `--refresh` to force a live rate-limit probe.
- If `script` is unavailable, Codex launch falls back to running without transcript capture.
- On Windows, transcript capture is optional. If no compatible `script` wrapper is installed, Codex still launches normally without transcript capture.
- Auth probe: synchronous subprocess call to `codex login status` or `claude auth status` before any interactive launch.
- Signal forwarding: `SIGINT`, `SIGTERM`, and `SIGHUP` are forwarded to the child process and produce clean exit codes.
- Test stack: Python built-in `unittest` runner with no test framework dependency.

---

## Getting Started

### Prerequisites

- Python 3.9+
- npm
- `codex` and/or `claude` CLI installed and available in your PATH

### Install

From npm:

```bash
npm install -g cdx-manager
```

With pipx:

```bash
pipx install cdx-manager
```

With uv:

```bash
uv tool install cdx-manager
```

On Windows with PowerShell:

```powershell
npm install -g cdx-manager
```

With the standalone PowerShell installer:

```powershell
irm https://raw.githubusercontent.com/AlexAgo83/cdx-manager/main/install.ps1 | iex
```

With the standalone GitHub installer:

```bash
curl -fsSL https://raw.githubusercontent.com/AlexAgo83/cdx-manager/main/install.sh | sh
```

For a specific version:

```bash
curl -fsSL https://raw.githubusercontent.com/AlexAgo83/cdx-manager/main/install.sh | CDX_VERSION=v0.3.4 sh
```

From source:

```bash
git clone <repo>
cd cdx-manager
make install
```

From source on Windows:

```powershell
git clone <repo>
cd cdx-manager
npm install -g .
```

`cdx` is now available globally. Changes to the source take effect immediately — no reinstall needed.

To uninstall:

```bash
make uninstall
```

To uninstall on Windows after `npm install -g`:

```powershell
npm uninstall -g cdx-manager
```

Alternatively, for a non-symlinked global source install:

```bash
npm install -g .
```

### Environment

By default, `cdx` stores all data under `~/.cdx/`. Override with:

```bash
export CDX_HOME=/path/to/custom/dir
```

Optional runtime knobs:

```bash
export CDX_CLAUDE_STATUS_MODEL=claude-haiku-4-5-20251001
export CDX_SCRIPT_BIN=script
export CDX_SCRIPT_ARGS='-q -F {transcript}'
```

PowerShell equivalents:

```powershell
$env:CDX_HOME = "C:\cdx-data"
$env:CDX_CLAUDE_STATUS_MODEL = "claude-haiku-4-5-20251001"
$env:CDX_SCRIPT_BIN = "script"
$env:CDX_SCRIPT_ARGS = "-q -F {transcript}"
```

Command Prompt equivalents:

```cmd
set CDX_HOME=C:\cdx-data
set CDX_CLAUDE_STATUS_MODEL=claude-haiku-4-5-20251001
set CDX_SCRIPT_BIN=script
set CDX_SCRIPT_ARGS=-q -F {transcript}
```

### Quick Start

```bash
# Register a Codex session
cdx add work

# Register a Claude session
cdx add claude personal

# List all sessions
cdx

# Launch a session
cdx work

# Check usage across all sessions
cdx status
```

---

## All Commands

| Command | Description |
|---|---|
| `cdx` | List all sessions with last-updated timestamps |
| `cdx --json` | List all sessions as a machine-readable JSON payload |
| `cdx <name>` | Launch a session (checks auth first) |
| `cdx <name> [--json]` | Launch a session; `--json` returns a structured success payload after the interactive run ends |
| `cdx add [provider] <name> [--json]` | Register a new session (`provider`: `codex` or `claude`, default: `codex`) |
| `cdx cp <source> <dest> [--json]` | Copy a session into another session name, overwriting the destination if it exists |
| `cdx ren <source> <dest> [--json]` | Rename a session and move its auth data |
| `cdx login <name> [--json]` | Re-authenticate a session (logout + login) |
| `cdx logout <name> [--json]` | Log out of a session |
| `cdx rmv <name> [--force] [--json]` | Remove a session and its auth data (prompts for confirmation unless `--force`) |
| `cdx clean [name] [--json]` | Clear launch transcript logs for one session or all sessions |
| `cdx doctor [--json]` | Inspect CLI dependencies, CDX_HOME permissions, missing state, orphan profiles, and pending quarantines |
| `cdx repair [--dry-run] [--force] [--json]` | Plan or apply safe repairs for missing state files, quarantines, and orphan profiles |
| `cdx notify <name> --at-reset [--poll seconds] [--once]` | Wait for a session reset time and send a desktop notification when due |
| `cdx notify --next-ready [--poll seconds] [--once]` | Wait until the recommended session is usable or needs a refresh after reset |
| `cdx status [--json] [--refresh]` | Show token usage table for all sessions; JSON keeps the same row-array shape and writes live Claude refresh warnings to stderr |
| `cdx status --small [--refresh]` / `cdx status -s [--refresh]` | Show compact token usage table without provider, blocking quota, credits, and updated columns |
| `cdx status <name> [--json] [--refresh]` | Show detailed usage breakdown for one session |
| `cdx --help` | Show usage |
| `cdx --version` | Show version |

---

## JSON Output

`cdx-manager` can be consumed by other apps through its CLI JSON contract.

Commands with machine-readable output:

- `cdx --json`
- `cdx status --json`
- `cdx status <name> --json`
- `cdx add ... --json`
- `cdx cp ... --json`
- `cdx ren ... --json`
- `cdx rmv ... --json`
- `cdx clean ... --json`
- `cdx login ... --json`
- `cdx logout ... --json`
- `cdx doctor --json`
- `cdx repair --json`
- `cdx notify ... --json`

Success payloads follow a shared envelope:

```json
{
  "ok": true,
  "action": "add",
  "message": "Created session work (codex)",
  "warnings": [],
  "session": {
    "name": "work"
  }
}
```

Errors use a shared stderr JSON envelope whenever `--json` is present:

```json
{
  "ok": false,
  "error": {
    "code": "invalid_usage",
    "message": "Usage: cdx status [--json] [--refresh] | ...",
    "exit_code": 1
  }
}
```

This makes `cdx-manager` usable from editor plugins, scripts, and desktop apps without scraping human-readable terminal output.

---

## Available Scripts

- `npm test`: run the Python test suite
- `npm run test:py`: run the Python unit tests directly
- `npm run lint`: byte-compile the Python sources and tests
- `npm run link`: link `cdx` globally for local development (`npm link`)
- `npm run unlink`: remove the global link

---

## Windows Support

- Supported install paths on Windows:
  - `npm install -g cdx-manager`
  - `pipx install cdx-manager`
  - `uv tool install cdx-manager`
  - `install.ps1`
- `install.sh` is Unix-only.
- `make install` and `make uninstall` are Unix-oriented convenience commands, not the default Windows path.
- `cdx` isolates Claude sessions on Windows by setting `HOME`, `USERPROFILE`, `HOMEDRIVE`, and `HOMEPATH`.
- Desktop notifications use PowerShell on Windows.
- Codex transcript capture is optional on Windows:
  - if a compatible `script` command is available and exposed via `CDX_SCRIPT_BIN`, `cdx` uses it
  - otherwise Codex launches without transcript capture and the session still works normally
- `cdx doctor` reports the transcript-capture fallback explicitly so missing `script` on Windows is visible without being treated as a hard failure.

---

## Project Structure

```text
bin/
  cdx                   # Entry point — shebang + main() call

src/
  cli.py                # Top-level command router
  cli_commands.py       # Command handlers and argument handling
  cli_render.py         # Terminal formatting, tables, colors, and errors
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

---

## Data Layout

All session data lives under `CDX_HOME` (default: `~/.cdx/`):

```text
~/.cdx/
  sessions.json             # Session registry (versioned, all sessions)
  state/
    <encoded-name>.json     # Per-session rehydration state
  profiles/
    <encoded-name>/         # Codex session: CODEX_HOME points here
      log/
        cdx-session.log     # Terminal transcript (written by script(1))
    <encoded-name>/
      claude-home/          # Claude session: HOME points here
        log/
          cdx-session.log
```

Session names are URL-encoded when used as directory or file names. CLI command names such as `add`, `status`, and `login` are reserved and cannot be used as session names.

---

## Troubleshooting

- **`cdx <name>` fails with "not authenticated"** — run `cdx login <name>` first.
- **`cdx add` succeeds but the session does not appear** — check that `CDX_HOME` is consistent between calls; a mismatch creates two separate registries.
- **Status shows `n/a` for all fields** — the session has not been launched yet, or the provider has not written any status output to its history files. Launch the session and run `/status` inside it at least once.
- **`cdx rmv` says "Removal requires confirmation in an interactive terminal"** — pass `--force` to bypass the prompt in non-interactive environments (scripts, CI).
- **`cdx login` hangs** — the provider's login flow requires a browser or device code. Follow the on-screen instructions in the terminal that opened.
- **`make install` says `npm link` is not found** — ensure Node.js and npm are installed and in your PATH.
- **On Windows, `doctor` warns that `script` is missing** — this is expected on many setups. Codex still launches, but transcript capture stays disabled unless you point `CDX_SCRIPT_BIN` to a compatible wrapper.

---

## Contributing

Contribution guidelines are available in [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE).
