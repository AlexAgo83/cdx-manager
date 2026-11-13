# CDX Manager 0.27.0

Release date: 2026-11-13

## New features

- `cdx send <name> <text>` delivers a message to a live interactive session
  through the provider's own protocol instead of typing into its terminal;
  `cdx send <name> --status [--json]` reports the turn state and
  `cdx send <name> --interrupt` interrupts the current remote turn. Turn it on
  per session with `cdx set <name> --remote-control on`, then relaunch it.
  With the option off, launch, resume and headless runs are unchanged (#140).
  - Claude: the TUI and a stream-json `--resume` run take turns on the same
    conversation. A message sent while the TUI is idle runs piloted, a message
    sent during a TUI turn waits for it, and a keypress brings the TUI back
    with every turn and its context.
  - Codex: the session starts a private app-server and attaches the TUI with
    `--remote`; `cdx send` starts turns on the TUI's thread, which renders them
    live.
  - Antigravity: one stream-json turn per message, resumed with
    `--conversation`. The conversation id comes from agy's own index or the
    piloted run's `init` event; interrupts are sent as a signal.
  - Each session writes an append-only event log with turn states and reply
    text. The control endpoint accepts only the session owner: a private Unix
    socket on Linux and macOS, a loopback endpoint with a per-session secret
    on Windows.
- On Windows, remote-controlled providers start from their native executables
  rather than npm `.cmd` shims, which cut multi-line arguments.

## Maintenance

- Four test groups no longer depend on the caller's environment: quota
  provenance compares instants rather than UTC offsets, the suite clears an
  inherited `RTK_DB_PATH`, and the real sandbox rtk test points `HOME` at the
  home that holds rtk.
