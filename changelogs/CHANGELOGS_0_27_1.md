# CDX Manager 0.27.1

Release date: 2026-11-13

## Improvements

- `cdx send <name> -` (or `--stdin`) reads the message from standard input,
  so callers no longer expose it in the process list. The positional form is
  unchanged, and an empty standard input is refused (#142).
- With remote control on, `cdx conversation --pid <TUI pid>` resolves a Codex
  session to the conversation its app-server writes. The launcher records the
  TUI and app-server pids in the session's private endpoint record, and the
  usual identity checks then apply to the app-server; sessions without remote
  control are unchanged (#142).
- Isolated workspaces mount the user's Python libraries, pipx and cargo
  read-only, add cargo and the newest nvm Node to PATH after the launch PATH,
  and list the user site-packages in PYTHONPATH (#141).
