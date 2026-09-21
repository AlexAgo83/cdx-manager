# CDX Manager 0.20.11

## Reliable handoff recovery

- Resolve Codex and Claude handoffs using the recorded native conversation ID and
  verify the workspace. An old transcript touched recently can no longer silently
  replace the intended conversation. Missing or stale identities return candidates;
  use `--source-conversation ID` to choose explicitly.
- Give the receiving agent access to the complete native transcript, including
  earlier decisions and tool evidence, instead of a flattened 120000-character tail.
  Each handoff has its own private entry with provenance, a preparation boundary and
  a checksum. Reusing an entry detects a deleted or rewritten source.
- Require the receiving agent to read repository instructions and their references,
  recover user decisions and authorization limits, verify current state, and show a
  concise recovery checkpoint before making changes. This is a prompt contract, not
  a guarantee of agent comprehension.
- Preserve workspace notes as supplementary context rather than overwriting them
  during handoff. Concurrent preparations retain separate entries; the target starts
  in the verified workspace.

## Compatibility notes

- `cdx handoff SOURCE TARGET --json` prepares without launching. JSON includes the
  entry path and source metadata, not transcript bodies or authentication data.
- `cdx handoff TARGET` reuses the prepared entry for that target and workspace. With
  no prepared entry, existing workspace notes remain available as explicitly labelled
  notes-only recovery.
- Automatic newest-log fallback is removed. For an intentional terminal-only
  fallback, pass `--source-transcript PATH` naming a source session launch log. This
  degraded mode cannot verify complete native history or the original workspace.
- Keep the original transcript available until recovery completes. The entry refers
  to it in place; it is not a transcript backup.

## Validation

- 1047 Python tests pass, including synthetic handoff regressions and mocked launches.
- Project lint and Logics corpus validation pass.
