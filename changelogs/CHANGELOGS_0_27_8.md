# CDX Manager 0.27.8

Release date: 2026-11-13

## Fixes

- Remote control no longer leaves for the terminal when the terminal only sends
  automatic replies (focus in/out, colour-scheme or cursor reports). Opening an
  HQ terminal view used to count as a keypress: the session went back to the
  TUI and the next chat message then killed and restarted Claude. Only a real
  keypress returns to the terminal now.
