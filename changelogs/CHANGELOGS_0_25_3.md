# CDX Manager 0.25.3

Release date: 2026-11-01

This patch release adds remote Codex execution over SSH and strengthens credential isolation for local and remote sandboxes.

## Features

- Run Codex on a Linux SSH worker with temporary credentials while keeping profiles, quota, history, costs, and run tracking on the controller. Support detached execution and clean up the temporary worker home after the run. (#78)

## Fixes and security

- Keep rotating refresh tokens on the controller and out of local and remote sandboxes. Use temporary access-token snapshots on verified memory-backed storage, refresh and validate credentials before launch, and fail explicitly when a snapshot expires. (#81)
- Upgrade cryptography and pytest to address security alerts while preserving Python 3.9 compatibility through a version-specific pytest requirement. (#80)
- Fix remote bootstrapping through Windows SSH shells and WSL without exceeding the command-line length limit. Check isolation prerequisites before sending credentials and refuse unsafe isolation without an unisolated fallback. (#79)

## Maintenance

- Record tray companion checksums for v0.25.2. (`4f810c3801418bc0ad8a480333cc0bdfda39383e`)
- Record release archive checksums for v0.25.2. (`b33eba1894d9cc68d395133848beccae38589a68`)
