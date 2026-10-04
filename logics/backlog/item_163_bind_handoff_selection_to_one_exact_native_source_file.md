## item_163_bind_handoff_selection_to_one_exact_native_source_file - Bind handoff selection to one exact native source file
> From version: 0.20.14
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 85%
> Complexity: Medium
> Theme: Handoff identity
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-10-04 17:38:53

# AI Context
- Summary: req_079 finding 1: duplicate IDs select the first filesystem match; the interactive chooser discards its chosen path and re-resolves only the ID.
- Keywords: bind, handoff, selection, exact, native, source, file
- Use when: Implementing bind handoff selection to one exact native source file.
- Skip when: Working outside this slice or adding deferred worktree management.

# Problem
- req_079 finding 1: duplicate IDs select the first filesystem match; the interactive chooser discards its chosen path and re-resolves only the ID.

# Scope
- In:
  - Validate all eligible identity/workspace matches before accepting an ID. Return actionable ambiguity when more than one qualifies.
  - Preserve and revalidate the exact candidate descriptor selected interactively; show enough path metadata to distinguish duplicate identities.
  - Provide an explicit native path selector (for example --source-native-transcript PATH) distinct from the existing degraded --source-transcript terminal option. Validate ownership, top-level eligibility, identity and workspace, and keep selectors mutually exclusive.
  - Preserve no-launch/no-mutation failure behavior, JSON preparation semantics, byte-integrity checks and target auth isolation. Extend CLI help/schema/docs/tests together.
  - Keep source availability and prompt-compliance limits explicit; preserve full original evidence rather than introducing copied/truncated summaries.
- Out:
  - No unrelated refactor, new service, or live provider/credential operation.

# Acceptance criteria
- AC1: Two valid files with one ID and different digests yield ambiguity for recorded/explicit-ID selection.
- AC2: Selecting candidate A prepares A even when native traversal would first find B; non-interactive exact-file selection has equivalent validation.
- AC3: Out-of-profile, sidechain, wrong-workspace, changed and cancelled selection cannot launch or replace a valid prepared pointer.
- AC4: Reuse still refuses changed/truncated/deleted source bytes, tolerates append beyond extent, and retains instruction-first recovery wording.

# AC Traceability
- request-AC8 -> This backlog slice. Proof deferred to implementation closeout; record the concrete regression and command result.
- request-AC10 -> This backlog slice. Proof deferred to implementation closeout; record the concrete regression and command result.
- request-AC11 -> This backlog slice. Proof deferred to implementation closeout; record the concrete regression and command result.
- request-AC12 -> This backlog slice. Proof deferred to implementation closeout; record the concrete regression and command result.

# Decision framing
- Product framing: Covered by the linked shared brief; this slice changes a user-visible reliability or reporting guarantee.
- Architecture framing: No separate ADR required; use existing persistence, transcript and CLI boundaries without a new subsystem.

# Links
- Product brief(s): `prod_056_trustworthy_local_recovery_and_usage_attribution`
- Architecture decision(s): (none yet)
- Request: `req_080_harden_reviewed_data_integrity_stats_accounting_and_handoff_recovery`
- Primary task(s): `task_085_orchestrate_review_hardening_across_persistence_stats_and_handoff`

# Priority
- Priority: Medium
- Rationale: prevent unintended historical context from reaching the target agent.

# Implementation entry points
- src/handoff.py, src/commands/launch.py, src/provider_background.py and src/interactive_usage.py.

# Dependencies and sequencing
- After item_164 literal-path discovery is validated; preserve existing source eligibility.

# Validation plan
- Start with `node bin/python-runner.js -m pytest -q test/test_handoff_transcript_py.py test/test_commands_launch_py.py test/test_cli_contract_py.py`.
- Add the smallest regression that fails on the reviewed defect; these existing suites alone are not proof of the fix.
- Finish with repository lint and the orchestration task cross-slice validation. Keep all fixture data synthetic and temporary.

# Implementation evidence
- Recorded or explicit conversation IDs are matched against all eligible native files. Duplicate matches return their exact paths and require an exact native selector or interactive choice. Interactive selection rechecks the selected file's digest and byte extent before preparing the pointer.
- `--source-native-transcript` validates top-level profile ownership and workspace separately from degraded terminal selection. Existing pointer integrity and no-launch checks remain in the handoff suite.
- Regressions: `test_duplicate_native_identity_requires_exact_path`, `test_interactive_duplicate_choice_preserves_selected_file`, and `test_exact_native_path_cli_prepares_selected_source`.
- `test_changed_interactive_choice_does_not_prepare_or_launch` verifies that a source changed between display and selection leaves the prepared pointer absent and never launches the target.
