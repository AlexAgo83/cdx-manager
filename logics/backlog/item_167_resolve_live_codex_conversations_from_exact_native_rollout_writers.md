## item_167_resolve_live_codex_conversations_from_exact_native_rollout_writers - Resolve live Codex conversations from exact native rollout writers
> From version: 0.26.8
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: High
> Theme: Operator workflow and runtime integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-11-08 00:46:11

# AI Context
- Summary: Resolve process-scoped conversations from a unique verified native rollout writer.
- Keywords: resolve, live, codex, conversations, exact, native, rollout, writers
- Use when: Maintaining native Codex PID resolution and its profile and lifetime boundaries.
- Skip when: Changing recency discovery or explicit-ID pagination.

# Problem
CDX 0.26.8 validates a native process but always returns unknown. Remote-ops cannot show or continue the exact live conversation. Use only the PID's native open-rollout evidence within the selected profile.

# Scope
- In:
  - Linux native Codex rollout descriptors, exact message reads, boundary regressions and CLI documentation
- Out:
  - releases, host installation, remote-ops consumer changes and process pagination

# Acceptance criteria
- AC1: A live native Codex PID with one writable profile-scoped rollout returns its native UUID and messages.
- AC2: Multiple writers, foreign profiles, invalid evidence, exited/reused processes and changing evidence expose no messages or guessed identity.
- AC3: No descendant, workspace or recency fallback participates; docs describe the native writer snapshot and required Tower measurement.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: The live kernel writer and CLI tests return the exact metadata UUID and messages.
- request-AC2 -> This backlog slice. Proof: Ambiguity, foreign profile, exit/reuse and inode/switch regression tests return unknown without entries.
- request-AC3 -> This backlog slice. Proof: No-cwd and no-descendant/search tests pass; docs/cli.md and the mission fragment state the native snapshot and Tower probe.

# Decision framing
- Product framing: Not needed
- Product signals: (none detected)
- Product follow-up: No product brief follow-up is expected based on current signals.
- Architecture framing: Not needed
- Architecture signals: (none detected)
- Architecture follow-up: No architecture decision follow-up is expected based on current signals.

# Links
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
- Request: `req_082_resolve_live_codex_conversations_from_exact_native_rollout_writers`
- Primary task(s): `task_087_resolve_live_codex_conversations_from_exact_native_rollout_writers`

# Priority
- Priority: High
- Rationale: Native identity absence blocks the remote-ops terminal conversation workflow.

# Notes
- Hybrid rationale: Derived from request `req_082_resolve_live_codex_conversations_from_exact_native_rollout_writers` and kept bounded to one coherent delivery slice.
- Source file: `logics/request/req_082_resolve_live_codex_conversations_from_exact_native_rollout_writers.md`.
- Mission 6fa0162a28; source evidence reports remote-ops mission 7af6402b87 blocked on native identity.
- Task `task_087_resolve_live_codex_conversations_from_exact_native_rollout_writers` was finished via `logics-manager flow finish task` on 2026-11-08.

# Executions
| When | Runner | Run id | Title | State | PR | Notes |
| --- | --- | --- | --- | --- | --- | --- |


# Tasks
- `task_087_resolve_live_codex_conversations_from_exact_native_rollout_writers`
