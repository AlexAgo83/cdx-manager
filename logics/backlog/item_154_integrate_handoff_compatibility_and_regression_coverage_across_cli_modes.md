## item_154_integrate_handoff_compatibility_and_regression_coverage_across_cli_modes - Integrate handoff compatibility and regression coverage across CLI modes
> From version: 0.20.10
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Handoff reliability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-09-21 12:38:02

# AI Context
- Integrate after the three core slices. Cover both existing CLI forms, prepare-only JSON, pinned workspace, synthetic regressions and truthful notes-only/degraded recovery.

# Problem
- Both CLI forms, JSON preparation, provider differences and shared-note compatibility need an explicit end-to-end contract.

# Scope
- In:
  - Retain cdx handoff SOURCE TARGET and cdx handoff TARGET; the latter uses a valid prepared entry when available or clearly labelled legacy notes-only input. It must not claim exact history when provenance is absent.
  - Keep --json prepare-only behavior (no provider launch), expose source ID/path/workspace/provenance and recovery mode without transcript bodies, and update usage/help plus CLI docs for --source-conversation and actionable failures.
  - Bind launch to the validated workspace; do not allow a later recent-directory prompt to redirect recovery silently. Check required source access before installation/launch.
  - For providers without supported native transcripts, retain only an explicitly selected available terminal artifact as degraded evidence with declared limitations; never call it full native recovery or select an arbitrary newest log.
  - Use anonymized fixtures and mocked provider launches. Cover malformed/truncated trailing JSONL records, long transcripts, active-source append boundaries, stale notes, overlapping preparations and all no-launch/no-overwrite failures. Run focused existing Python tests and the repository-required verification commands; record evidence without real account access.
- Out:
  - No unrelated provider resume, authentication, quota routing or memory-system redesign.

# Acceptance criteria
- AC1: Both command forms and JSON mode have documented, tested outcomes for exact-source, notes-only and degraded cases.
- AC2: End-to-end synthetic tests reproduce the observed old-conversation selection and missing-instruction prompt failures and prevent their recurrence.
- AC3: Authentication is unchanged, source resolution failures do not launch or replace context, and every launch uses the verified workspace.
- AC4: CLI docs include a short recovery example and limitations; project and Logics checks pass with AC evidence ready for closeout.

# AC Traceability
- request-AC2 -> This backlog slice. Proof: Planned: Missing/ambiguous identity and explicit selection failure fixtures. Execution evidence deferred to implementation.
- request-AC3 -> This backlog slice. Proof: Planned: Complete transcript access and entry provenance assertions. Execution evidence deferred to implementation.
- request-AC4 -> This backlog slice. Proof: Planned: Instruction-first prompt ordering assertions for both providers. Execution evidence deferred to implementation.
- request-AC5 -> This backlog slice. Proof: Planned: Recovery checkpoint and current-evidence prompt assertions. Execution evidence deferred to implementation.
- request-AC6 -> This backlog slice. Proof: Planned: Preserved notes and explicitly labelled notes-only recovery assertions. Execution evidence deferred to implementation.
- request-AC7 -> This backlog slice. Proof: Planned: CLI mode, workspace and authentication preservation assertions. Execution evidence deferred to implementation.
- request-AC8 -> This backlog slice. Proof: Planned: Synthetic regression suite and recorded project validation outcomes. Execution evidence deferred to implementation.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_055_reliable_transcript_first_handoff_recovery`
- Architecture decision(s): (none yet)
- Request: `req_075_make_handoff_recover_the_exact_conversation_and_repository_instructions_before_acting`
- Primary task(s): `task_083_deliver_reliable_transcript_first_handoff_from_source_resolution_through_verified_recovery`

# Priority
- Priority: High
- Rationale: Recovery errors can send an agent into the wrong task or omit standing operational constraints.

# Tasks
- `task_083_deliver_reliable_transcript_first_handoff_from_source_resolution_through_verified_recovery`

# Notes
- Task `task_083_deliver_reliable_transcript_first_handoff_from_source_resolution_through_verified_recovery` was finished via `logics-manager flow finish task` on 2026-09-21.
