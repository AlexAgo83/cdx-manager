# CDX Manager 0.26.0

Release date: 2026-11-03

This release adds optional profile concurrency settings for automatic missions
and incremental JSON access to interactive conversations.

## Automatic mission concurrency

- Add an optional per-profile `launch.max_parallel` setting through `cdx set
  <name> --max-parallel N`, accepting integers from 0 to 5. Zero excludes a
  profile from automatic missions; an unset value leaves the scheduling client's
  default in effect. Expose the setting in list JSON, status JSON, and profile
  settings, and clear it with `cdx unset <name> --max-parallel`. Scheduling
  clients enforce this setting; the existing `cdx run --max-parallel` limit
  remains separate. (#101)

## Interactive conversation reading

- Add `cdx conversation <name> --json` and the reusable `read_conversation`
  Python function to read Codex, Claude, and Antigravity transcripts
  incrementally with bounded reads and opaque pagination cursors. Return
  normalized messages and tool activity summaries while omitting tool bodies,
  attachments, metadata, and reasoning, and redacting recognized credentials.
  Report missing transcripts as unavailable and Ollama terminal captures as
  unsupported; require a cursor reset after rotation or truncation. (#100)

## Maintenance

- Record tray companion checksums for v0.25.9. (`6d0a825b9649da9aead3379e6411e3959cd30a77`)
- Record release archive checksums for v0.25.9. (`e3682ad8aed14d75c3c686a0c6027f53cfe81cd3`)
