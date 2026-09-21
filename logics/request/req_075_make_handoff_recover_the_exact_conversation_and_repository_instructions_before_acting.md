## req_075_make_handoff_recover_the_exact_conversation_and_repository_instructions_before_acting - Make handoff recover the exact conversation and repository instructions before acting
> From version: 0.20.10
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: High
> Theme: Handoff reliability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-09-21 12:15:44

# AI Context
- Observed failures combine wrong native conversation selection, lossy transcript transport and missing repository instructions. Deliver the four linked slices together; private incident data must not enter fixtures.

# Needs
- An incoming agent must recover the actual source conversation, repository instructions, user decisions and unfinished work without requiring the outgoing agent to write a summary before its quota expires.
- Replace the authoritative truncated shared-context transcript with a small provenance-bearing entry document pointing to the full native transcript, followed by instruction-first recovery before changes.

# Context
- Read-only investigation on 2026-09-21 found a Claude-to-Claude handoff selecting an older conversation whose last event preceded the intended conversation by about eleven and a half hours. The recipient recovered the intended plan only after operator intervention. Names, tenant details and private transcript contents are deliberately omitted.
- The recipient first read repository AGENTS.md about 28 minutes after launch; the missing access procedure was at the top of that file. It explicitly acknowledged the omission. This establishes a recovery failure, not proof that better context alone prevents all later agent errors.
- _latest_handoff_transcript_path ranks files by mtime; workspace detection recognizes Codex session_meta only. Recursive discovery can include Claude subagents and index/history files. Existing conversation_transcript resolves an exact native identity and should be reused.
- _read_handoff_transcript keeps the final 120000 characters after lossy extraction. The observed artifact began inside worker logs, and the recipient tool truncated its first read again. Codex tool records are excluded; Claude tool-result content can survive inside user records, so extraction is not equivalent across providers.
- _handoff_launch_prompt requests shared-context first and immediate continuation, without repository instruction recovery. handle_handoff overwrites workspace context and installs one shared-context.md per target profile. Both one-name and two-name forms must be covered.
- The older completed item_064 intended identity-anchored handoff, but current handoff selection still bypasses it. This is a corrective delivery grounded in current code, not a reopening of completed resume work.

# Acceptance criteria
- AC1: Codex and Claude handoff resolve the recorded source conversation identity and verify its normalized workspace; file modification time never silently overrides identity or selects a subagent, index, history file or unrelated workspace.
- AC2: Missing, stale, mismatched or ambiguous identity produces bounded candidate diagnostics and an explicit source selection path; non-interactive callers get an actionable structured error. Invalid or cancelled selection does not launch a provider or overwrite context.
- AC3: A small handoff entry document identifies source and target, provider, native conversation ID, workspace, preparation time, transcript format/path and recovery instructions. The complete source transcript remains available for bounded reads with tools and results intact; no 120000-character tail is authoritative.
- AC4: The target prompt requires applicable AGENTS.md and CLAUDE.md plus their required references such as LOGICS.md and logics/instructions.md to be read before reconstructing the task and before modifications, independently of provider auto-loading.
- AC5: Recovery reconstructs objective, latest user corrections, decisions, authorization boundaries, pending work and relevant tool evidence, then checks current repository/operational state read-only and emits a concise recovery checkpoint before acting. Clear existing authorization permits continuation without a mandatory confirmation round.
- AC6: Optional shared notes remain dated supplementary context, are not silently overwritten by automatic handoff preparation, and cannot replace source identity or live verification. Legacy one-name context handoff remains explicitly identifiable as notes-only when it has no transcript provenance.
- AC7: Existing handoff forms and JSON preparation semantics remain documented and tested; preparation preserves source/target authentication, launches only when expected, pins the recovery workspace, and reports unsupported or unavailable native sources without pretending to restore complete context.
- AC8: Anonymized regression fixtures cover wrong mtime selection, workspace mismatch, subagents, missing identity, long transcripts, instruction ordering, notes compatibility and no-launch failures. Focused tests and required project/Logics checks pass; docs distinguish prompt requirements from enforceable guarantees.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_055_reliable_transcript_first_handoff_recovery`
- Architecture decision(s): (none yet)

# References
- src/cli_helpers.py
- src/commands/launch.py
- src/context_store.py
- src/interactive_usage.py
- src/provider_background.py
- src/provider_runtime.py
- src/cli_args.py
- test/test_handoff_transcript_py.py
- test/test_commands_launch_py.py
- docs/cli.md
- Historical background: completed native-session-identity work (backlog 064); not implementation lineage for this request.

# Backlog
- `item_151_resolve_handoff_sources_by_native_conversation_identity_and_workspace`
- `item_152_replace_truncated_handoff_context_with_a_provenance_bearing_transcript_entry`
- `item_153_require_repository_instructions_and_an_evidence_based_checkpoint_before_handoff_actions`
- `item_154_integrate_handoff_compatibility_and_regression_coverage_across_cli_modes`
