## req_059_record_interactive_codex_and_claude_cli_token_usage - Record interactive Codex and Claude CLI token usage
> From version: 0.19.1
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Usage observability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: record, interactive, codex, claude, cli, token, usage
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Needs
- CDX persists token usage for headless runs, but interactive launches of Codex and Claude are absent from the same history and statistics.
- Users need to retrieve their own interactive CLI token usage through the existing CDX history and statistics commands, without parsing terminal output themselves.
- Codex and Claude already write local provider transcripts for interactive sessions; CDX launches already provide an isolated provider home and a CDX session name to child hooks.

# Context
- Current Codex rollout JSONL files emit cumulative token_count events with total_token_usage fields for input, cached input, output, reasoning output, and total tokens.
- Current Claude transcript JSONL files include an assistant message usage object for each model response, including input, cache creation/read, and output tokens.
- The interactive terminal transcript captured by script is presentation output and must not become the accounting source when a provider JSONL source is available.
- CDX already provisions lifecycle hooks for interactive Codex and Claude launches, and cdx history plus cdx stats already render and aggregate persisted usage fields.
- Provider transcript formats are implementation artifacts, so parsers must be tolerant of incomplete lines and unknown fields, report unavailable data honestly, and avoid emitting prompt, tool, or assistant content into CDX usage records.

# Acceptance criteria
- AC1: An interactive Codex session launched through CDX records the latest cumulative provider token totals, including input, cached input, output, reasoning, and total, without parsing ANSI terminal capture.
- AC2: An interactive Claude session launched through CDX records token totals from its provider transcript without double-counting repeated hook invocations or cache fields.
- AC3: Usage capture runs at a reliable lifecycle boundary for both providers and preserves a final session total when the user exits, clears, or resumes away from an interactive session.
- AC4: Captured interactive usage is persisted in the existing launch-history-compatible data model and appears through existing cdx history and cdx stats text and JSON commands without adding a parallel user-facing reporting command.
- AC5: Missing, malformed, incomplete, or changed provider transcript data never breaks an interactive provider turn, invents a token value, or stores conversation content in the usage record.
- AC6: Focused parser, deduplication, lifecycle provisioning, persistence, history/statistics, and provider launch checks pass.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_046_interactive_cli_usage_accounting`
- Architecture decision(s): (none yet)

# References
- README.md
- src/agent_notify.py
- src/provider_runtime.py
- src/provider_background.py
- src/run_usage.py
- src/commands/status.py
- src/session_service.py
- test/test_agent_notify_py.py
- test/test_provider_background_py.py
- test/test_runtime_py.py

# Backlog
- `item_117_capture_and_normalize_interactive_provider_token_snapshots`
- `item_118_persist_interactive_usage_in_existing_cdx_history_and_statistics`
