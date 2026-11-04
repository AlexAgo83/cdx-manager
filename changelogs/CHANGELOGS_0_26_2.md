# CDX Manager 0.26.2

## Fixes

- Scope conversation recency fallback to `--cwd PATH` (the process working
  directory by default), using Claude project folders or Codex `session_meta.cwd`.
  Support `--since ISO` to exclude transcripts modified before session start.
  Return `unavailable` / `no_conversation_yet` when no candidate matches instead
  of showing another project. Add `resolution_scope` without changing
  `resolution_method` or exact conversation ID lookup semantics.

- Read only Claude-compatible `user` and `assistant` records with `message`,
  preserving their tool calls and results. Ignore all other record types,
  including Claude Code request blobs that repeat user prompts without dates.
- Apply the same allowlist to oversized records; retain only `response_item`
  records for Codex so event copies cannot appear as conversation entries.
  Ignore oversized records when the bounded prefix cannot establish their type
  and message metadata.
- Cover the reported Claude Code 2.1.317 request-blob shape, dated messages,
  tools, cursor pagination and ignored metadata for all structured providers.
