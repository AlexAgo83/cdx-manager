# CDX Manager 0.27.7

Release date: 2026-11-13

## Fixes

- Two launches of the same profile no longer block each other's remote
  control. Each launch keeps its own turn-state record
  (`state/agents/launches/<name>@<pid>.json`), so a busy launch no longer keeps
  the other one's messages queued; `cdx agents` still lists one row per session.
- A launcher that receives SIGHUP or SIGTERM while it starts no longer leaves its
  remote-control endpoint behind: the signal handlers are installed before the
  endpoint files are written.
- The release CI is green again on Windows and macOS, so this release is also
  published to PyPI and npm (0.27.5 and 0.27.6 were GitHub-only).
