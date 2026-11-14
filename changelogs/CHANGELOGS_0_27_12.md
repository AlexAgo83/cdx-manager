# CDX Manager 0.27.12

Release date: 2026-11-14

## Fixes

- A message sent to a busy Claude session through the cdx channel now appears in
  its conversation. Claude Code absorbs it into the running turn and records it as
  a queued command whose origin is the channel; the conversation reader only
  accepted queued commands typed by a person, so HQ kept such messages "en
  attente" although the session had read them.
