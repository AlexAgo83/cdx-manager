# CDX Manager 0.27.19

Release date: 2026-11-19

## Fixes

- The remote event log of a channel-driven Claude session now records every
  turn, not only those opened by a channel message: a turn typed at the
  keyboard (origin `human`) opens with its text as the prompt, and a turn that a
  background task's notification starts opens marked `background`, with no
  prompt. A remote chat (Jarvis HQ) no longer loses the replies written in
  those turns. User lines without an origin (older Claude Code) are still left
  to the TUI.
