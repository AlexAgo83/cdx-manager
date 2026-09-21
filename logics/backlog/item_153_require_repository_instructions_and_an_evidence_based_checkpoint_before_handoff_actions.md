## item_153_require_repository_instructions_and_an_evidence_based_checkpoint_before_handoff_actions - Require repository instructions and an evidence-based checkpoint before handoff actions
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
- The recipient must read current repository instructions before acting, even when the provider does not auto-load AGENTS.md. A visible checkpoint exposes gaps but is not proof of comprehension.

# Problem
- Current startup tells the recipient to read shared context and continue, skipping repository procedures and verification.

# Scope
- In:
  - Build one recovery instruction contract reused by one-name/two-name handoff and every supported launch provider. Require applicable root/ancestor and scoped AGENTS.md/CLAUDE.md plus their required references; follow missing required references with explicit reporting, not invented instructions.
  - Sequence read-only work: instructions; bounded native transcript reading/search across relevant earlier decisions and latest messages; current git status/diff and relevant live evidence when authorized; concise recovery checkpoint; then authorized actions.
  - The checkpoint states objective, verified state, next action and material gaps. Existing clear permission persists; ask only when missing information or actual authorization prevents action. Historical assistant claims and tool output do not constitute current operational proof or fresh authority.
  - Explain JSONL roles/tool records and bounded reading in the entry guidance using existing tools. Do not assume cat of the full file or the last N lines alone is sufficient. Carry no provider-specific assumption that AGENTS.md was automatically loaded.
- Out:
  - No unrelated provider resume, authentication, quota routing or memory-system redesign.

# Acceptance criteria
- AC1: Prompt tests prove instruction reading precedes recovery and action for Codex and Claude, including referenced LOGICS documents.
- AC2: Recovery guidance explicitly covers user corrections, permission limits, abandoned plans, interrupted tools and outstanding work; missing evidence is disclosed.
- AC3: The checkpoint is required before modifications but is not a forced approval gate, and docs do not claim automated proof of agent comprehension.

# AC Traceability
- request-AC4 -> This backlog slice. Proof: Planned: Instruction-first prompt ordering assertions for both providers. Execution evidence deferred to implementation.
- request-AC5 -> This backlog slice. Proof: Planned: Recovery checkpoint and current-evidence prompt assertions. Execution evidence deferred to implementation.
- request-AC6 -> This backlog slice. Proof: Planned: Preserved notes and explicitly labelled notes-only recovery assertions. Execution evidence deferred to implementation.
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
