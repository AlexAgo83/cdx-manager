## item_152_replace_truncated_handoff_context_with_a_provenance_bearing_transcript_entry - Replace truncated handoff context with a provenance-bearing transcript entry
> From version: 0.20.10
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 80%
> Complexity: Medium
> Theme: Handoff reliability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-09-21 12:26:58

# AI Context
- Separate generated recovery metadata from user-maintained context_store notes. The native transcript remains the evidence source; each handoff gets its own entry path and preparation extent.

# Problem
- A 120000-character tail and subsequent tool truncation discard evidence, while generated handoffs overwrite shared notes.

# Scope
- In:
  - Generate a small dedicated handoff artifact with exact source metadata, workspace, prepared-at timestamp and full transcript path; preserve native JSONL and tool evidence rather than embedding flattened history.
  - Use an artifact unique to the handoff and pass its exact path to the target. Do not use a single mutable profile-wide shared-context.md as authoritative transport. Keep generated artifacts outside the repository and never copy credentials.
  - Record the readable transcript extent at preparation (for example byte length) so recovery distinguishes the transferred conversation state from later appends. Read-only access to the original is sufficient; no unconditional transcript duplication.
  - Point to optional notes with provenance and freshness caveats. On unavailable source, stop with a recoverable diagnostic rather than presenting notes as a complete transcript. Document paths/availability and retention using existing storage conventions.
- Out:
  - No unrelated provider resume, authentication, quota routing or memory-system redesign.

# Acceptance criteria
- AC1: Long source transcripts remain fully reachable, including early decisions and tool results, without a hard tail cutoff or a huge initial prompt.
- AC2: Metadata binds the entry to one source, target, workspace and preparation extent; two prepared handoffs do not overwrite each other.
- AC3: Existing workspace notes and source files remain unchanged; no credentials are copied or transcript bodies emitted in normal CLI/JSON output.

# AC Traceability
- request-AC3 -> This backlog slice. Proof: Planned: Complete transcript access and entry provenance assertions. Execution evidence deferred to implementation.
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
