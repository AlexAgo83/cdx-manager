## item_151_resolve_handoff_sources_by_native_conversation_identity_and_workspace - Resolve handoff sources by native conversation identity and workspace
> From version: 0.20.10
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Handoff reliability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-09-21 12:15:44

# AI Context
- Start at _latest_handoff_transcript_path and reuse conversation_transcript. Claude metadata differs from Codex session_meta; validate both formats and reject subagent identity.

# Problem
- mtime-based selection can pick an old conversation; Claude workspace and subagent boundaries are not enforced.

# Scope
- In:
  - Reuse conversation_transcript and existing provider lookup before extending discovery. Validate identity, provider and realpath workspace against transcript metadata, not a guessed path alone.
  - For absent/invalid identity, show bounded top-level candidates with ID, workspace and actual last event time. Add an explicit --source-conversation ID selector; interactive ambiguity may prompt, non-interactive ambiguity returns candidates without launching. Never silently fall back from a recorded but missing identity.
  - Exclude nested subagents and history/index artifacts. Reject workspace mismatch rather than silently switching projects. Missing/corrupt/unreadable metadata produces a clear diagnostic.
- Out:
  - No unrelated provider resume, authentication, quota routing or memory-system redesign.

# Acceptance criteria
- AC1: Exact identity wins when an older file has a newer mtime, for Codex and Claude.
- AC2: Other-workspace and nested subagent transcripts never win automatic discovery; no candidate is inferred solely from recency.
- AC3: Explicit selection validates identity and workspace; cancellation and failures produce no artifact/context/session mutation or launch.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: Planned: Exact Codex/Claude identity and workspace selection fixtures. Execution evidence deferred to implementation.
- request-AC2 -> This backlog slice. Proof: Planned: Missing/ambiguous identity and explicit selection failure fixtures. Execution evidence deferred to implementation.
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
