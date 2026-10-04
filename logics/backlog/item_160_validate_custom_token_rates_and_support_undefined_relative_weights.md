## item_160_validate_custom_token_rates_and_support_undefined_relative_weights - Validate custom token rates and support undefined relative weights
> From version: 0.20.14
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Pricing robustness
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-10-04 17:41:51

# AI Context
- Summary: req_078 finding 3: zero, nonnumeric, negative and nonfinite overrides are not handled consistently; weighted ratios divide by input price.
- Keywords: validate, custom, token, rates, support, undefined, relative, weights
- Use when: Implementing validate custom token rates and support undefined relative weights.
- Skip when: Working outside this slice or adding deferred worktree management.

# Problem
- req_078 finding 3: zero, nonnumeric, negative and nonfinite overrides are not handled consistently; weighted ratios divide by input price.

# Scope
- In:
  - Validate each supplied rate as a finite nonnegative number, explicitly rejecting booleans and malformed structures; surface actionable configuration errors in text and JSON without tracebacks.
  - For zero-input tariffs, compute USD directly from valid rates; mark COST~ unavailable where its ratio is undefined. Preserve free USD=0 as priced rather than missing.
  - Adapt aggregation, sorting and rendering to explicit unavailable weighted values without fallback inventing a paid denominator or crashing. Describe partial weighting when combining known and undefined weights.
  - Resolve the price table once per stats calculation and use that same table/provenance for per-entry totals and footer; preserve documented cache-read override behavior.
- Out:
  - No unrelated refactor, new service, or live provider/credential operation.

# Acceptance criteria
- AC1: Invalid string, negative, NaN/infinity and malformed entries produce a named actionable error and valid JSON on --json.
- AC2: Zero-input models can report a finite nonnegative USD cost while relative weight is explicitly unavailable; all-zero free tariffs remain supported.
- AC3: Valid existing default and override computations remain numerically unchanged.

# AC Traceability
- request-AC5 -> This backlog slice. Proof: Implemented in `0b34fb3`; `test_zero_input_price_keeps_currency_but_not_undefined_weights` passed in the 1076-test Python suite. See Implementation evidence below.
- request-AC11 -> This backlog slice. Proof: Implemented in `0b34fb3`; `test_zero_input_price_keeps_currency_but_not_undefined_weights` passed in the 1076-test Python suite. See Implementation evidence below.
- request-AC12 -> This backlog slice. Proof: Implemented in `0b34fb3`; `test_zero_input_price_keeps_currency_but_not_undefined_weights` passed in the 1076-test Python suite. See Implementation evidence below.

> Shared proof: AC5, AC11, AC12

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
- Rationale: prevent reporting exceptions and misleading monetary results from documented configuration.

# Implementation entry points
- src/run_usage.py and src/commands/status.py.

# Dependencies and sequencing
- After item_158 and item_159 accounting contracts stabilize; defines weighted availability consumed by item_162.

# Validation plan
- Start with `node bin/python-runner.js -m pytest -q test/test_usage_weighting_py.py test/test_commands_status_py.py`.
- Add the smallest regression that fails on the reviewed defect; these existing suites alone are not proof of the fix.
- Finish with repository lint and the orchestration task cross-slice validation. Keep all fixture data synthetic and temporary.

# Implementation evidence
- `CDX_TOKEN_PRICES` now rejects malformed JSON, missing fields and nonnumeric, negative or nonfinite rates with a named error. A zero input price retains direct USD pricing while undefined relative weights are excluded from `COST~` and counted as uncovered.
- `test_invalid_override_rates_fail_actionably` and `test_zero_input_price_keeps_currency_but_not_undefined_weights` cover the boundaries.

# Tasks
- `task_085_orchestrate_review_hardening_across_persistence_stats_and_handoff`

# Notes
- Task `task_085_orchestrate_review_hardening_across_persistence_stats_and_handoff` was finished via `logics-manager flow finish task` on 2026-10-04.
