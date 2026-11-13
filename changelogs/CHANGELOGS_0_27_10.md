# CDX Manager 0.27.10

Release date: 2026-11-13

## Fixes

- Claude remote control no longer stops the terminal session. A `cdx send`
  message used to kill the Claude TUI, run the turn in a separate stream-json
  process and relaunch the TUI, which killed every background task the session
  was running (test suites, waits on remote hosts) and could cut a turn. Messages
  now enter the live TUI through cdx's own Claude Code channel (`server:cdx`),
  so background tasks, permission prompts and slash commands keep working, and
  the chat and the terminal show the same conversation. In tmux, cdx accepts
  Claude Code's development-channel warning at launch.
