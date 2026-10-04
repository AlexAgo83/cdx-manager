## item_161_persist_observed_model_attribution_for_headless_usage_pricing - Persist observed model attribution for headless usage pricing
> From version: 0.20.14
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Headless observability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-10-04 17:41:51

# AI Context
- Summary: req_078 secondary observation: headless usage is stored without usage_model, leaving supported usage unpriced even when serving-model evidence is available.
- Keywords: persist, observed, model, attribution, headless, usage, pricing
- Use when: Implementing persist observed model attribution for headless usage pricing.
- Skip when: Working outside this slice or adding deferred worktree management.

# Problem
- req_078 secondary observation: headless usage is stored without usage_model, leaving supported usage unpriced even when serving-model evidence is available.

# Scope
- In:
  - Extract model identity from supported provider output or the exact run transcript alongside normalized usage, including per-model output where actually provided.
  - Persist attribution per attempt and expose it through history/stats without storing conversation content. Never infer serving identity solely from configured --model.
  - For genuinely mixed models, use a supported measured breakdown if available; otherwise preserve and explicitly label the documented estimate or leave unavailable attribution unpriced.
  - Cover normal headless runs and the existing detached/background completion paths that feed reporting; avoid adding unsupported provider promises.
- Out:
  - No unrelated refactor, new service, or live provider/credential operation.

# Acceptance criteria
- AC1: A synthetic headless response naming a supported model and usage becomes a priced history/stat row under the correct session.
- AC2: Missing/unknown serving model stays explicitly unpriced; a requested model alone is not evidence.
- AC3: Model data and usage remain paired to their actual failover attempt, including failures with usage.

# AC Traceability
- request-AC6 -> This backlog slice. Proof: Implemented in `0b34fb3`; `test_headless_model_must_be_observed_and_unmixed` passed in the 1076-test Python suite. See Implementation evidence below.
- request-AC3 -> This backlog slice. Proof: Implemented in `0b34fb3`; `test_headless_model_must_be_observed_and_unmixed` passed in the 1076-test Python suite. See Implementation evidence below.
- request-AC11 -> This backlog slice. Proof: Implemented in `0b34fb3`; `test_headless_model_must_be_observed_and_unmixed` passed in the 1076-test Python suite. See Implementation evidence below.
- request-AC12 -> This backlog slice. Proof: Implemented in `0b34fb3`; `test_headless_model_must_be_observed_and_unmixed` passed in the 1076-test Python suite. See Implementation evidence below.

> Shared proof: AC6, AC3, AC11, AC12

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
- Rationale: close measured price-coverage gaps after attempt accounting is stable.

# Implementation entry points
- src/run_usage.py, src/provider_background.py, src/commands/runs.py and src/session_service.py.

# Dependencies and sequencing
- Depends on item_158 attempt accounting and item_160 price/availability rules.

# Validation plan
- Start with `node bin/python-runner.js -m pytest -q test/test_commands_runs_py.py test/test_provider_background_py.py test/test_usage_weighting_py.py`.
- Add the smallest regression that fails on the reviewed defect; these existing suites alone are not proof of the fix.
- Finish with repository lint and the orchestration task cross-slice validation. Keep all fixture data synthetic and temporary.

# Implementation evidence
- Blocking headless output and delegated Claude transcript closeout now carry a serving model only when one model is observed alongside usage. Mixed or missing observed models remain unpriced; configured requested model is not used as evidence.
- The failover regression verifies per-attempt models; `test_headless_model_must_be_observed_and_unmixed` and `test_model_attribution_requires_one_observed_model` cover missing and mixed reports.

# Tasks
- `task_085_orchestrate_review_hardening_across_persistence_stats_and_handoff`

# Notes
- Task `task_085_orchestrate_review_hardening_across_persistence_stats_and_handoff` was finished via `logics-manager flow finish task` on 2026-10-04.
