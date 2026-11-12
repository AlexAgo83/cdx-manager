# CDX Manager 0.26.14

Release date: 2026-11-12

## Fixes

- Resume a waiting Claude session's agent state when `PostToolUse` reports tool
  completion. Also subscribe to `PreToolUse` to clear idle waits before a long
  tool runs. Tool events preserve other states, including failures and confirmed
  limits, and avoid rewriting an already working record. Preserve the prompt
  preview and existing alert behavior.
- Install the new hooks alongside operator hooks without replacing them or
  adding duplicates on subsequent launches.
