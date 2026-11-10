## task_087_resolve_live_codex_conversations_from_exact_native_rollout_writers - Resolve live Codex conversations from exact native rollout writers
> From version: 0.26.8
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Owner: codex
> Indicators reviewed: 2026-11-08 00:46:11

# AI Context
- Summary: Resolve process-scoped conversations from a unique verified native rollout writer.
- Keywords: resolve, live, codex, conversations, exact, native, rollout, writers
- Use when: Maintaining native Codex PID resolution and its profile and lifetime boundaries.
- Skip when: Changing recency discovery or explicit-ID pagination.

# Definition of Done (DoD)
- [x] The backlog scope is implemented.
- [x] Acceptance criteria are covered.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# Backlog
- `item_167_resolve_live_codex_conversations_from_exact_native_rollout_writers`

# Acceptance criteria
- AC1: A live native Codex PID with one writable profile-scoped rollout returns its native UUID and messages.
- AC2: Multiple writers, foreign profiles, invalid evidence, exited/reused processes and changing evidence expose no messages or guessed identity.
- AC3: No descendant, workspace or recency fallback participates; docs describe the native writer snapshot and required Host A measurement.

# AC Traceability
- request-AC1 -> This task. Proof: The live kernel writer and CLI tests return the exact metadata UUID and messages.
- request-AC2 -> This task. Proof: Ambiguity, foreign profile, exit/reuse and inode/switch regression tests return unknown without entries.
- request-AC3 -> This task. Proof: No-cwd and no-descendant/search tests pass; docs/cli.md and the mission fragment state the native snapshot and Host A probe.

# Plan
- [x] Resolve and recheck the sole writable native rollout within the selected profile.
- [x] Read the verified exact file and retain process cursor refusal.
- [x] Cover positive reads, ambiguity, profile boundaries, exit/reuse and evidence changes; update CLI docs.
- [x] Complete repository validation and record the Host A measurement requirement.

# Validation
- Final Logics lint, audit and diff whitespace check: passed; six existing audit warnings outside this change.
- `uv run --extra dev npm run lint`: passed after moving temporary third-party toolchain files outside the checkout.
- Full Python suite: 1956 passed, 5 skipped; initial environment interference corrected before successful retry.
- Rust tray suite: 99 passed. npm package dry-run and Python wheel build passed.
- Native kernel fixtures cover exact messages and lifetime/profile boundaries; authenticated Host A launch/resume/switch measurement remains pending as documented in the mission fragment.
- Finish workflow executed on 2026-11-08.
- Linked backlog/request close verification passed.

# Report
- Implemented the bounded native writer snapshot. The mission fragment records the assumption, local checks and remaining authenticated Host A probe. No release is authorized in this mission.
- Finished on 2026-11-08.
- Linked backlog item(s): `item_167_resolve_live_codex_conversations_from_exact_native_rollout_writers`
- Related request(s): `req_082_resolve_live_codex_conversations_from_exact_native_rollout_writers`

# Links
- Request: `req_082_resolve_live_codex_conversations_from_exact_native_rollout_writers`
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# Executions
| When | Runner | Run id | Title | State | PR | Notes |
| --- | --- | --- | --- | --- | --- | --- |
