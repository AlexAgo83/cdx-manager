# CDX Manager 0.23.0

This release gives external orchestrators a stable way to read runs, live sessions and profile locations, so they no longer need to scan processes, parse provider output or rely on cdx's directory layout.

## Runs

- `cdx runs --running --json` returns every run still in progress, without the `--limit` cap, so a concurrency check always sees the full count.
- `cdx run-report` now includes `final_message`: the run's last assistant message, read from Claude's result or Codex's last agent message.
- The accepted run `kind` values are documented with `cdx runs`; `cdx schema --json` remains their source.

## Sessions and profiles

- `cdx sessions --json` lists interactive sessions launched through cdx that are still running, with their process id, provider, working directory, start time and conversation id.
- `cdx sessions --all --json` adds idle accounts. Each row includes `profile_dir` and `transcripts_dir`; the credential directory stays hidden.

## Resume

- `cdx can-resume <name> --conversation <id>` checks one exact conversation on Claude or Codex.
- `cdx resume <name> --conversation <id>` reopens that conversation. A missing conversation is refused with `conversation_not_found` rather than replaced by the most recent one.
