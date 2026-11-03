# CDX Manager 0.26.1

Release date: 2026-11-03

## Fixes

- Preserve the profile's interactive conversation across local, detached, remote,
  and continued headless runs. Keep headless Claude identities in run records
  and history, and skip interactive Codex identity observation for run history.
  (#103)
- Let `cdx conversation` use the latest local transcript when the profile's
  recorded conversation ID has no transcript on this host. Explicit
  `--conversation` lookups remain exact. Expose `resolution_method` as
  `conversation_id`, `recency`, or `null`; recency remains best effort. (#103)

## Maintenance

- Record tray companion checksums for v0.26.0.
  (`c942c9f6fdcfabd1ad0442e46f978da3b548971f`)
- Record release archive checksums for v0.26.0.
  (`9a43f53d7294ecb254bd65aea214831bcd1486fb`)
