## item_159_measure_interactive_usage_at_real_launch_boundaries_without_a_history_cap - Measure interactive usage at real launch boundaries without a history cap
> From version: 0.20.14
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 85%
> Complexity: High
> Theme: Usage measurement
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-10-04 17:37:04

# AI Context
- Summary: req_078 finding 2: previous end snapshots include intervening unmanaged activity; callers also supply only the last 50 history rows.
- Keywords: measure, interactive, usage, real, launch, boundaries, history, cap
- Use when: Implementing measure interactive usage at real launch boundaries without a history cap.
- Skip when: Working outside this slice or adding deferred worktree management.

# Problem
- req_078 finding 2: previous end snapshots include intervening unmanaged activity; callers also supply only the last 50 history rows.

# Scope
- In:
  - Capture a starting snapshot at the pre-provider launch boundary when the intended transcript is identifiable; compute the ending increment against that snapshot.
  - Use exact identity where possible. Newly created transcripts can use a proven empty baseline; if discovery or concurrent writers make ownership uncertain, leave measured usage absent and record a bounded reason instead of guessing.
  - Remove the arbitrary 50-entry dependency for any necessary historical lookup; avoid rescanning all transcripts or introducing a daemon/database.
  - Cover source/npm and installed package call paths, normal exit, errors, resume, transcript rotation/shrink and first-sighting cases. Keep unknown different from zero.
- Out:
  - No unrelated refactor, new service, or live provider/credential operation.

# Acceptance criteria
- AC1: A prior 10-token run, 50 intervening tokens and 20 new tokens records 20 for the new run, not 70.
- AC2: Resuming after more than 50 other history entries preserves a valid current-launch baseline and correct measured delta.
- AC3: Overlapping or unresolvable transcript ownership is detected or explicitly reported as uncertain; no confident cross-run attribution is invented.
- AC4: Existing sequential resume, identity, normalization and shrink regressions pass.

# AC Traceability
- request-AC4 -> This backlog slice. Proof deferred to implementation closeout; record the concrete regression and command result.
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
- Rationale: prevent incorrect attribution to a run and reporting period.

# Implementation entry points
- src/commands/launch.py, src/interactive_usage.py and src/session_store.py.

# Dependencies and sequencing
- After the High-priority wave; coordinate history metadata with item_158 before updating rendering.

# Validation plan
- Start with `node bin/python-runner.js -m pytest -q test/test_usage_delta_py.py test/test_interactive_usage_py.py test/test_commands_launch_py.py test/test_usage_backfill_py.py`.
- Add the smallest regression that fails on the reviewed defect; these existing suites alone are not proof of the fix.
- Finish with repository lint and the orchestration task cross-slice validation. Keep all fixture data synthetic and temporary.

# Implementation evidence
- Native cumulative usage is sampled before launch for a known conversation identity, then differenced at exit. A newly created transcript can use its own total; an existing unmatched transcript is marked uncertain and remains unmeasured. History lookup no longer stops at 50 rows.
- `test_launch_boundary_excludes_intervening_transcript_growth` verifies that 50 intervening tokens are excluded from a 20-token run. `test_prior_cumulative_beyond_fifty_history_rows_is_found` covers the old lookup cap.
- A detected second live runtime on the same session marks attribution `overlapping_session` and leaves usage absent; `test_overlapping_session_leaves_usage_unattributed` covers that boundary.
