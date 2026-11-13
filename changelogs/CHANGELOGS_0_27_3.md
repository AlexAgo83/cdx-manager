# CDX Manager 0.27.3

Release date: 2026-11-13

## Fixes

- `cdx conversation` no longer shows the AGENTS.md instructions and
  environment context that Codex injects before the first message as user
  turns, for normal and remote-controlled sessions (#144).
- Two launches of the same session no longer overwrite each other's
  remote-control files. Each launch owns `<name>@<pid>.endpoint.json` and its
  token; `<name>.endpoint.json` keeps the same content and points to the newest
  live launch, and is handed back to an older one when the newest exits.
  `cdx send <name> --pid <pid>` targets a specific launch, and the runtime
  record keeps older running launches (#144).
