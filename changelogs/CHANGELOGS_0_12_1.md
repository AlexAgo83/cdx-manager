# CDX Manager 0.12.1

## Highlights

- Added `cdx update all` to inventory and safely update the installed provider CLIs, RTK, and Ponytail across Codex profiles.
- Made account handoffs use native provider transcripts before terminal capture, preserving actionable conversation instead of terminal noise.

## Changes

### Workstation updates

`cdx update all` now reports installed versions and session setup, asks once before applying its plan, and shows progress plus the command and error output when an action fails. It follows the actual installer provenance of each CLI, including the Claude Code cask rather than the separate Claude desktop app.

RTK is enabled for sessions that lack it when available. Ponytail marketplaces and plugins are checked per Codex profile; current Codex marketplace caches without a `last_revision` field are resolved from their Git checkout.

### Reliable handoffs

Cross-session handoffs now prefer native JSONL transcripts and retain only user and assistant messages. Script-captured terminal logs remain a fallback, but no longer displace structured provider conversation or tool-output noise into the shared context.

## Validation

- `npm run lint`
- `npm test`
- `logics-manager lint --require-status`
- `logics-manager audit --group-by-doc`
