## req_082_resolve_live_codex_conversations_from_exact_native_rollout_writers - Resolve live Codex conversations from exact native rollout writers
> From version: 0.26.8
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: General
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Owner: codex
> Indicators reviewed: 2026-11-08 00:46:10

# AI Context
- Summary: Resolve process-scoped conversations from a unique verified native rollout writer.
- Keywords: resolve, live, codex, conversations, exact, native, rollout, writers
- Use when: Maintaining native Codex PID resolution and its profile and lifetime boundaries.
- Skip when: Changing recency discovery or explicit-ID pagination.

# Needs
- CDX 0.26.8 validates a native process but always returns unknown. Remote-ops cannot show or continue the exact live conversation. Use only the PID's native open-rollout evidence within the selected profile.

# Context
- Mission 6fa0162a28; source evidence reports remote-ops mission 7af6402b87 blocked on native identity.
- Scope excludes releases, host installation, remote-ops consumer changes and process pagination.

# Acceptance criteria
- AC1: A live native Codex PID with one writable profile-scoped rollout returns its native UUID and messages.
- AC2: Multiple writers, foreign profiles, invalid evidence, exited/reused processes and changing evidence expose no messages or guessed identity.
- AC3: No descendant, workspace or recency fallback participates; docs describe the native writer snapshot and required Tower measurement.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed: Linux /proc access is required; an authenticated Tower measurement remains separate from fixture proof.

# Companion docs
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# References
- `src/process_conversation.py`
- `test/test_process_conversation_py.py`
- `docs/cli.md`

# Backlog
- `item_167_resolve_live_codex_conversations_from_exact_native_rollout_writers`

# Executions
| When | Runner | Run id | Title | State | PR | Notes |
| --- | --- | --- | --- | --- | --- | --- |
