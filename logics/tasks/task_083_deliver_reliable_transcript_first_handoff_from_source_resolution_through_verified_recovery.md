## task_083_deliver_reliable_transcript_first_handoff_from_source_resolution_through_verified_recovery - Deliver reliable transcript-first handoff from source resolution through verified recovery
> From version: 0.20.10
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 80%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-09-21 12:26:58
> Owner: Codex

# AI Context
- Recover from abrupt quota exhaustion without relying on the outgoing agent. Execute identity resolution, transcript transport, repository instruction recovery and CLI integration in dependency order.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Wave 1 (High): reproduce identity selection failures with synthetic Codex and Claude fixtures; reuse exact transcript resolution and establish source/workspace validation and explicit candidate selection. Keep existing resume behavior unchanged.
- [ ] 2. Wave 2 (High, depends on wave 1): create the small handoff entry artifact, preserve access to the complete transcript and isolate it from optional workspace notes; handle concurrent target-profile launches without replacing another handoff artifact.
- [ ] 3. Wave 3 (High, depends on wave 2): apply the instruction-first recovery contract to both handoff forms and provider launch prompts; pin workspace and require a concise objective/state/next-action checkpoint before edits.
- [ ] 4. Wave 4 (High, depends on waves 1-3): integrate JSON/errors and legacy notes-only behavior, cover unsupported providers and failure atomicity, update CLI docs and run focused plus repository-required checks using synthetic data and mocked launches.
- [ ] 5. Record AC-by-AC evidence and relevant Logics updates at each meaningful wave. Do not launch real provider sessions, modify private transcripts or perform tenant operations for tests. Validate closeout and settle the product brief only after implementation and checks are complete.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_151_resolve_handoff_sources_by_native_conversation_identity_and_workspace`
- `item_152_replace_truncated_handoff_context_with_a_provenance_bearing_transcript_entry`
- `item_153_require_repository_instructions_and_an_evidence_based_checkpoint_before_handoff_actions`
- `item_154_integrate_handoff_compatibility_and_regression_coverage_across_cli_modes`

# Definition of Done (DoD)
- [ ] All four linked backlog slices are implemented and request AC1-AC8 have executable evidence.
- [ ] Exact-source recovery, full transcript access, instruction-first prompts and legacy CLI compatibility are delivered and documented.
- [ ] Focused regression tests, required project checks, Logics lint/audit and closeout validation pass; no private transcripts or credentials are committed.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_151_resolve_handoff_sources_by_native_conversation_identity_and_workspace`. Proof deferred to slice closeout.
- request-AC2 -> `item_151_resolve_handoff_sources_by_native_conversation_identity_and_workspace`. Proof deferred to slice closeout.
- request-AC7 -> `item_151_resolve_handoff_sources_by_native_conversation_identity_and_workspace`. Proof deferred to slice closeout.
- request-AC8 -> `item_151_resolve_handoff_sources_by_native_conversation_identity_and_workspace`. Proof deferred to slice closeout.
- request-AC3 -> `item_152_replace_truncated_handoff_context_with_a_provenance_bearing_transcript_entry`. Proof deferred to slice closeout.
- request-AC6 -> `item_152_replace_truncated_handoff_context_with_a_provenance_bearing_transcript_entry`. Proof deferred to slice closeout.
- request-AC7 -> `item_152_replace_truncated_handoff_context_with_a_provenance_bearing_transcript_entry`. Proof deferred to slice closeout.
- request-AC8 -> `item_152_replace_truncated_handoff_context_with_a_provenance_bearing_transcript_entry`. Proof deferred to slice closeout.
- request-AC4 -> `item_153_require_repository_instructions_and_an_evidence_based_checkpoint_before_handoff_actions`. Proof deferred to slice closeout.
- request-AC5 -> `item_153_require_repository_instructions_and_an_evidence_based_checkpoint_before_handoff_actions`. Proof deferred to slice closeout.
- request-AC6 -> `item_153_require_repository_instructions_and_an_evidence_based_checkpoint_before_handoff_actions`. Proof deferred to slice closeout.
- request-AC8 -> `item_153_require_repository_instructions_and_an_evidence_based_checkpoint_before_handoff_actions`. Proof deferred to slice closeout.
- request-AC2 -> `item_154_integrate_handoff_compatibility_and_regression_coverage_across_cli_modes`. Proof deferred to slice closeout.
- request-AC3 -> `item_154_integrate_handoff_compatibility_and_regression_coverage_across_cli_modes`. Proof deferred to slice closeout.
- request-AC4 -> `item_154_integrate_handoff_compatibility_and_regression_coverage_across_cli_modes`. Proof deferred to slice closeout.
- request-AC5 -> `item_154_integrate_handoff_compatibility_and_regression_coverage_across_cli_modes`. Proof deferred to slice closeout.
- request-AC6 -> `item_154_integrate_handoff_compatibility_and_regression_coverage_across_cli_modes`. Proof deferred to slice closeout.
- request-AC7 -> `item_154_integrate_handoff_compatibility_and_regression_coverage_across_cli_modes`. Proof deferred to slice closeout.
- request-AC8 -> `item_154_integrate_handoff_compatibility_and_regression_coverage_across_cli_modes`. Proof deferred to slice closeout.

# Validation
- npm run lint: passed. npm test: 1047 passed. Focused python3 -m pytest test/test_handoff_transcript_py.py test/test_commands_launch_py.py -q: 64 passed. git diff --check: passed. Coverage includes stale recorded IDs, newer mtime on old transcripts, workspace/subagent exclusion, malformed metadata, partial JSONL tails, full early tool evidence, source rewrite detection, concurrent preparations, preserved notes/auth sentinel, JSON no-launch, pinned workspace, cancellation and explicit degraded fallback.

# Report
- Implemented exact native identity/workspace selection, explicit candidate choice, complete transcript references with preparation extent and SHA-256, unique private handoff entries, preserved supplementary notes, and instruction-first recovery/checkpoint prompts. Both CLI forms and prepare-only JSON are covered. README.md is the existing CLI documentation; the scaffold reference to nonexistent docs/cli.md was corrected. Synthetic fixtures and mocked launches only; no live account or tenant operations. Existing native resume behavior is unchanged.

# Links
- Request: `req_075_make_handoff_recover_the_exact_conversation_and_repository_instructions_before_acting`
- Product brief(s): `prod_055_reliable_transcript_first_handoff_recovery`
- Architecture decision(s): (none yet)
