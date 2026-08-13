# CDX Manager 0.19.2

## Features

- Record Codex and Claude interactive CLI token usage, including cached input tokens, in existing run history and status statistics.

## Fixes

- Make detached-run registry persistence durable and lock acquisition bounded on POSIX and Windows.
- Bound interactive transcript discovery and parsing while preserving fail-open behavior.
- Verify tray tests, macOS CI coverage, and installable npm/wheel package artifacts before release.
