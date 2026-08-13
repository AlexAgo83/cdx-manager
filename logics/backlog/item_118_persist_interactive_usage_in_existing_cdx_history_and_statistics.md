## item_118_persist_interactive_usage_in_existing_cdx_history_and_statistics - Persist interactive usage in existing CDX history and statistics
> From version: 0.19.1
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Usage observability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: persist, interactive, usage, existing, cdx, history, statistics
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- cdx history and cdx stats already display persisted usage but only headless runs currently populate it.
- Interactive hook provisioning is currently coupled to notification preference, so accounting must not depend on desktop notifications being enabled.

# Scope
- In:
  - Persist normalized interactive usage with the existing launch-history-compatible record shape, keyed to the CDX session and provider session identity.
  - Provision the minimal accounting hooks for interactive Codex and Claude independently from optional notification delivery, respecting Codex hook-trust requirements.
  - Reuse existing cdx history and cdx stats renderers and JSON payloads; update only their documentation and tests as needed to make interactive coverage explicit.
  - Ensure the record contains only identifiers, timestamps, provider/session metadata, and usage totals needed by current reporting.
- Out:
  - A new analytics database, background daemon, remote upload, or automatic provider polling.
  - Changing existing headless run usage semantics.
  - Collecting usage for CLI sessions that were not launched through CDX.

# Acceptance criteria
- AC1: A completed interactive launch contributes one usage-bearing record that cdx history and cdx stats return in text and JSON output.
- AC2: Repeated turn hooks update the same interactive session record rather than creating duplicate usage entries.
- AC3: Interactive accounting works when notifications are disabled and does not alter notification behaviour when they are enabled.
- AC4: The documented commands state that interactive Codex and Claude token usage is included when the provider exposes a readable local transcript.
- AC5: Focused persistence, command-contract, and provider-hook provisioning tests pass.

# AC Traceability
- request-AC3 -> This backlog slice. Proof: AC1: A completed interactive launch contributes one usage-bearing record that cdx history and cdx stats return in text and JSON output.
- request-AC4 -> This backlog slice. Proof: AC2: Repeated turn hooks update the same interactive session record rather than creating duplicate usage entries.
- request-AC5 -> This backlog slice. Proof: AC3: Interactive accounting works when notifications are disabled and does not alter notification behaviour when they are enabled.
- request-AC6 -> This backlog slice. Proof: AC4: The documented commands state that interactive Codex and Claude token usage is included when the provider exposes a readable local transcript.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_046_interactive_cli_usage_accounting`
- Architecture decision(s): (none yet)
- Request: `req_059_record_interactive_codex_and_claude_cli_token_usage`
- Primary task(s): `task_070_orchestrate_interactive_codex_and_claude_cli_usage_accounting`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.

# Tasks
- `task_070_orchestrate_interactive_codex_and_claude_cli_usage_accounting`

# Notes
- Task `task_070_orchestrate_interactive_codex_and_claude_cli_usage_accounting` was finished via `logics-manager flow finish task` on 2026-08-13.
