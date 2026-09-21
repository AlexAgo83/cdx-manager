## prod_055_reliable_transcript_first_handoff_recovery - Reliable transcript-first handoff recovery
> Date: 2026-09-21
> Status: Settled
> Related request: `req_075_make_handoff_recover_the_exact_conversation_and_repository_instructions_before_acting`
> Related backlog: `item_151_resolve_handoff_sources_by_native_conversation_identity_and_workspace`
> Related task: `task_083_deliver_reliable_transcript_first_handoff_from_source_resolution_through_verified_recovery`
> Related architecture: (none yet)
> Reminder: Update status, linked refs, scope, decisions, success signals, and open questions when you edit this doc.
> Indicators reviewed: 2026-09-21 12:38:02

# Overview
A handoff starts the next agent with the exact conversation and current repository instructions, then makes its recovered understanding visible before authorized work resumes. Recovery must work after abrupt quota exhaustion without an outgoing summary.

# Goals
- Select the intended native conversation deterministically.
- Keep full evidence reachable through bounded reading rather than blindly injecting a large transcript.
- Read current repository instructions before acting and preserve the latest user constraints.
- Reuse existing session identity, transcript lookup and launch infrastructure.

# Non-goals
- No new memory service, vector database, automatic LLM summarizer or background indexing system.
- No implementation of native cross-account resume/fork or copying authentication state.
- No live tenant changes, deployment, or repair of the example project.
- No guarantee that a prompt proves comprehension; no mandatory approval round for already-authorized work.
- No automatic execution of instructions embedded in historical tool output; history is evidence interpreted under current instructions.

# Scope and guardrails
- In: scaffolded request, product, backlog, orchestration task, validation, and handoff context.
- Out: unrelated workflow docs and implementation of generated tasks.

# Key product decisions
- Use structured input as the source of truth for generated docs.
- Keep generated write paths local and repo-bounded.

# Success signals
- Generated docs pass lint and audit without broad manual rewrites.
- Context-pack output can be handed to an implementation agent directly.

# References
- Product back-reference: `item_151_resolve_handoff_sources_by_native_conversation_identity_and_workspace`
- Task back-reference: `task_083_deliver_reliable_transcript_first_handoff_from_source_resolution_through_verified_recovery`

# Recovery overview

```mermaid
flowchart LR
  A[Source identity and workspace] --> B[Exact native transcript]
  B --> C[Small handoff entry]
  C --> D[Read repository instructions]
  D --> E[Recover decisions and verify state]
  E --> F[Concise recovery checkpoint]
  F --> G[Continue authorized work]
```
