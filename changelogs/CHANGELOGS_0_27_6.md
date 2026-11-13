# CDX Manager 0.27.6

Release date: 2026-11-13

## Fixes

- `cdx send --interrupt` stops a piloted Claude turn. The CLI ignored the
  stream-json interrupt request, so cdx now ends the run, as for Antigravity;
  the next message resumes the same conversation.
- The "Returning to the terminal after the current turn" notice is printed
  once, however many keys are pressed.

## Improvements

- `cdx conversation <antigravity session> --conversation <id>` reads agy's
  plain transcript, which includes turns typed in the agy TUI, not only the
  ones sent through `cdx send`.
