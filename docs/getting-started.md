# Getting started

## Prerequisites

- Node.js 18+ with npm
- Python 3.9+
- `codex`, `claude`, `agy`, and/or `ollama` CLI installed and available in your PATH

On Windows, the npm launcher looks for Python in this order: `py -3`, `python`, then `python3`. Make sure at least one of those commands resolves to Python 3.

## Install

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
Invoke-WebRequest https://raw.githubusercontent.com/AlexAgo83/cdx-manager/main/install.ps1 -OutFile install.ps1
# Optional: set CDX_SHA256 before running if you have a trusted checksum.
# Set CDX_ALLOW_UNVERIFIED=1 only if you intentionally accept an unverified archive.
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

With the standalone GitHub installer:

```bash
curl -fsSL https://raw.githubusercontent.com/AlexAgo83/cdx-manager/main/install.sh -o install.sh
# Optional: set CDX_SHA256 before running if you have a trusted checksum.
# Set CDX_ALLOW_UNVERIFIED=1 only if you intentionally accept an unverified archive.
sh install.sh
```

For a specific version:

```bash
curl -fsSL https://raw.githubusercontent.com/AlexAgo83/cdx-manager/main/install.sh -o install.sh
CDX_VERSION=v0.8.0 sh install.sh
```

From source:

```bash
git clone <repo>
cd cdx-manager
make install
```

For local development, install the Python toolchain as well:

```bash
python3 -m pip install -e ".[dev]"
```

From source on Windows:

```powershell
git clone <repo>
cd cdx-manager
npm install -g .
```

`cdx` is now available globally. Changes to the source take effect immediately — no reinstall needed.

To update an installed copy later:

```bash
cdx update
```

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

Security note:

- The standalone installers resolve official release checksums from the tagged GitHub Release asset `release-archives.json`.
- You can still override verification explicitly through `CDX_SHA256`.
- If no checksum is available, standalone installers fail closed unless `CDX_ALLOW_UNVERIFIED=1` is set; that override prints a prominent warning before continuing.
- Prefer `npm`, `pipx`, or `uv` when you want registry-backed install flows.
- If you use the standalone script, download it first, inspect it, and prefer a release with the official checksum asset attached.


## Environment

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

## Quick Start

```bash
# Register a Codex session
cdx add work

# Register a Claude session
cdx add claude personal

# Register an Ollama session
cdx add ollama local --model llama3.2

# List all sessions
cdx

# Launch a session
cdx work

# Check usage across all sessions
cdx status

# Pick the best session using the same priority logic as status
cdx next

# Notify when the next cooling-down assistant is ready
cdx ready

# Inspect CDX_HOME and profile disk usage
cdx disk
cdx disk profiles --candidates
```
