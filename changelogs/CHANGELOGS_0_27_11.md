# CDX Manager 0.27.11

Release date: 2026-11-14

## Fixes

- Messages sent to a Claude session through the cdx channel now appear in its
  conversation. Claude Code records them as meta lines wrapped in
  `<channel source="cdx">`, so the conversation reader dropped them and HQ kept
  every remote message "en attente de la session" with a Retirer action, even
  though the session had received it. The reader now keeps a line that is a whole
  channel delivery, shows its text without the wrapper, and still hides Claude
  Code's own meta notes.
