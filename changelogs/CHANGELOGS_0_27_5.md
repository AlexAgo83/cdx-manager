# CDX Manager 0.27.5

Release date: 2026-11-13

## Fixes

- A remote-controlled Claude or Antigravity session returns to the terminal
  after messages were sent during a turn. Claude folds such messages into the
  running turn and ends it with a single result, so counting one turn per
  message never reached zero: the key press never gave the TUI back and the
  session stayed busy. cdx now writes one message per turn and sends the next
  one after the result that ends the current turn.
- `cdx conversation` shows prompts queued during a print-mode turn as user
  entries, so a message sent from a remote client no longer looks unanswered.
