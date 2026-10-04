## item_156_preserve_live_profiles_on_early_force_import_credential_failures - Preserve live profiles on early force import credential failures
> From version: 0.20.14
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Profile recovery
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-10-04 17:17:36

# AI Context
- Summary: req_077 finding 1: src/session_backup.py moves the live profile before a fallible keychain read outside rollback protection. A refusal leaves the registered live path absent.
- Keywords: preserve, live, profiles, early, force, import, credential, failures
- Use when: Implementing preserve live profiles on early force import credential failures.
- Skip when: Working outside this slice or adding deferred worktree management.

# Problem
- req_077 finding 1: src/session_backup.py moves the live profile before a fallible keychain read outside rollback protection. A refusal leaves the registered live path absent.

# Scope
- In:
  - Complete the credential preflight before destructive movement, or encompass all post-move failures in the existing rollback boundary; reuse current recovery helpers.
  - Preserve original files, metadata, state and credential backend on early and late failures. If recovery fails, retain recovery data and report its location without secret material.
  - Add failure injection at the initial read, directory move and rollback boundaries using temporary profiles and mocked credential access.
- Out:
  - No unrelated refactor, new service, or live provider/credential operation.

# Acceptance criteria
- AC1: The reproduced early keychain denial leaves the profile sentinel at the original path and record/state unchanged.
- AC2: Existing merge credential precedence, late rollback and incomplete-recovery regressions remain green.
- AC3: Failure diagnostics preserve actionable recovery information and contain no credential values.

# AC Traceability
- request-AC1 -> This backlog slice. Proof deferred to implementation closeout; record the concrete regression and command result.
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
- Priority: High
- Rationale: restore safety of an operation that can disrupt an existing authenticated session.

# Implementation entry points
- src/session_backup.py and src/claude_credentials.py.

# Dependencies and sequencing
- None; first delivery slice.

# Validation plan
- Start with `node bin/python-runner.js -m pytest -q test/test_profile_data_safety_py.py test/test_commands_backup_py.py`.
- Add the smallest regression that fails on the reviewed defect; these existing suites alone are not proof of the fix.
- Finish with repository lint and the orchestration task cross-slice validation. Keep all fixture data synthetic and temporary.

# Implementation evidence
- The live Claude credential is read before a forced profile move. A denied read now leaves the profile sentinel, record, state and credential unchanged.
- Regression: `test_early_force_import_keychain_denial_preserves_live_profile`; existing late rollback and incomplete-recovery tests remain in the same focused run.
- Wave 1 focused run: `node bin/python-runner.js -m pytest -q test/test_profile_data_safety_py.py test/test_commands_backup_py.py` — 37 passed.
