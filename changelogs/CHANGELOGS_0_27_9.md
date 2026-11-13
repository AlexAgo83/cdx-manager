# CDX Manager 0.27.9

Release date: 2026-11-13

## Fixes

- Remote control returns to the TUI on its own once a `cdx send` turn is over
  and nothing is queued. An HQ chat message used to leave the terminal on the
  stream view until the operator pressed a key in it. A key press still asks
  for the same return.
