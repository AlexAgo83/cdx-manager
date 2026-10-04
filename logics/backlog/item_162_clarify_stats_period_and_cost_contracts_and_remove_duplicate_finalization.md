## item_162_clarify_stats_period_and_cost_contracts_and_remove_duplicate_finalization - Clarify stats period and cost contracts and remove duplicate finalization
> From version: 0.20.14
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Stats contract
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-10-04 17:41:51

# AI Context
- Summary: req_078 secondary observations: duplicated finalization; overlapping periods are non-additive; relative weights are not dollars; partial coverage and approximate tariffs need explicit interpretation.
- Keywords: clarify, stats, period, cost, contracts, remove, duplicate, finalization
- Use when: Implementing clarify stats period and cost contracts and remove duplicate finalization.
- Skip when: Working outside this slice or adding deferred worktree management.

# Problem
- req_078 secondary observations: duplicated finalization; overlapping periods are non-additive; relative weights are not dollars; partial coverage and approximate tariffs need explicit interpretation.

# Scope
- In:
  - Remove the duplicate row-finalization loop and retain one normalization path, validated against representative existing history.
  - Preserve whole-run overlap filtering; document and expose that daily windows can double-include a crossing run. Do not fabricate proportional token splits.
  - Document live/completed coverage, unknown versus zero, usage_runs/priced_runs, attempt versus logical-run counts, weighted availability and price provenance. Use additive JSON metadata where the existing payload cannot convey these distinctions.
  - Keep model-relative COST~ and its existing ordering policy explicit rather than claiming USD ranking; keep partial unpriced coverage visible.
  - Preserve documented current-table repricing and mixed-model/long-context/service-tier/cache-TTL limitations; label estimates, not invoices. No independent rate refresh is part of this scope.
- Out:
  - No unrelated refactor, new service, or live provider/credential operation.

# Acceptance criteria
- AC1: One finalization pass yields unchanged valid totals; absent measurements and undefined weights remain distinguishable from zero.
- AC2: A cross-midnight fixture demonstrates documented non-additivity in adjacent periods and a single inclusion in their combined period.
- AC3: Text, JSON schema/tests and README consistently describe partial model pricing, current-table provenance and completed/attempt accounting.

# AC Traceability
- request-AC7 -> This backlog slice. Proof: Implemented in `0b34fb3`; `test_cross_midnight_run_is_whole_in_each_overlapping_period` passed in the 1076-test Python suite. See Implementation evidence below.
- request-AC11 -> This backlog slice. Proof: Implemented in `0b34fb3`; `test_cross_midnight_run_is_whole_in_each_overlapping_period` passed in the 1076-test Python suite. See Implementation evidence below.
- request-AC12 -> This backlog slice. Proof: Implemented in `0b34fb3`; `test_cross_midnight_run_is_whole_in_each_overlapping_period` passed in the 1076-test Python suite. See Implementation evidence below.

> Shared proof: AC7, AC11, AC12

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
- Rationale: stabilize interpretation after measurement/pricing changes, without replacing the accounting model.

# Implementation entry points
- src/commands/status.py, src/cli_args.py and README.md.

# Dependencies and sequencing
- Depends on item_158, item_159, item_160 and item_161; this is the final stats contract pass.

# Validation plan
- Start with `node bin/python-runner.js -m pytest -q test/test_commands_status_py.py test/test_usage_weighting_py.py test/test_unvouched_usage_py.py`.
- Add the smallest regression that fails on the reviewed defect; these existing suites alone are not proof of the fix.
- Finish with repository lint and the orchestration task cross-slice validation. Keep all fixture data synthetic and temporary.

# Implementation evidence
- Removed the duplicate row-finalization loop. `weighted_runs` and `unweighted_runs` expose partial relative-cost coverage; JSON `accounting` describes attempt counts, whole-run period overlap and price source. README now distinguishes attempt history, live/completed coverage, partial USD pricing and current-table repricing.
- `test_cross_midnight_run_is_whole_in_each_overlapping_period` validates non-additive adjacent periods; the existing stats and weighting suites verify totals and presentation.

# Tasks
- `task_085_orchestrate_review_hardening_across_persistence_stats_and_handoff`

# Notes
- Task `task_085_orchestrate_review_hardening_across_persistence_stats_and_handoff` was finished via `logics-manager flow finish task` on 2026-10-04.
