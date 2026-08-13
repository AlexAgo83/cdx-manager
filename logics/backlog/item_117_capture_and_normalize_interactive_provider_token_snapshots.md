## item_117_capture_and_normalize_interactive_provider_token_snapshots - Capture and normalize interactive provider token snapshots
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
- Keywords: capture, normalize, interactive, provider, token, snapshots
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- Interactive sessions expose structured usage in provider-owned JSONL artifacts, but CDX currently only normalizes headless JSON output.
- Lifecycle hooks may fire repeatedly and a transcript may be mid-write, so naïve summing or a strict parser can miscount usage or disrupt an agent turn.

# Scope
- In:
  - Add small provider-specific readers for the latest Codex cumulative token_count snapshot and summed Claude assistant usage records.
  - Normalize values to the existing input_tokens, output_tokens, reasoning_tokens, and total_tokens contract while retaining cached input only where the persisted schema supports it.
  - Use Stop and SessionEnd lifecycle events as appropriate, with idempotent high-water-mark handling for repeated events.
  - Cover valid, incomplete, malformed, changed, and duplicate transcript cases with focused tests.
- Out:
  - Changing provider CLI protocol or requiring OpenTelemetry for ordinary local interactive usage.
  - Reading or storing prompts, tool input, assistant text, or terminal screen captures.
  - Building a live dashboard or a new reporting command.

# Acceptance criteria
- AC1: Codex parsing selects the latest valid cumulative total_token_usage snapshot and does not add cached input into total tokens.
- AC2: Claude parsing sums usage once per assistant response using the same cache accounting policy as existing CDX usage normalization.
- AC3: Re-running capture for the same session is idempotent and never reduces a previously recorded valid cumulative total.
- AC4: A malformed or partially written record is ignored without raising from the hook path.
- AC5: Focused parser and lifecycle tests pass.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: Codex parsing selects the latest valid cumulative total_token_usage snapshot and does not add cached input into total tokens.
- request-AC2 -> This backlog slice. Proof: AC2: Claude parsing sums usage once per assistant response using the same cache accounting policy as existing CDX usage normalization.
- request-AC3 -> This backlog slice. Proof: AC3: Re-running capture for the same session is idempotent and never reduces a previously recorded valid cumulative total.
- request-AC5 -> This backlog slice. Proof: AC4: A malformed or partially written record is ignored without raising from the hook path.
- request-AC6 -> This backlog slice. Proof: AC5: Focused parser and lifecycle tests pass.

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
