## item_158_account_for_every_headless_failover_attempt_under_its_actual_session - Account for every headless failover attempt under its actual session
> From version: 0.20.14
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: High
> Theme: Usage attribution
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-10-04 17:41:51

# AI Context
- Summary: req_078 finding 1: the loop overwrites run_info and records final-attempt usage under the original session.
- Keywords: account, headless, failover, attempt, under, actual, session
- Use when: Implementing account for every headless failover attempt under its actual session.
- Skip when: Working outside this slice or adding deferred worktree management.

# Problem
- req_078 finding 1: the loop overwrites run_info and records final-attempt usage under the original session.

# Scope
- In:
  - Preserve attempt accounting with run identity and attempt identity; retain session, timestamps, duration, status and normalized usage before advancing.
  - Keep one logical registry run and its occupancies. Define stats launches as existing history execution records, with each failover attempt counted once; document the distinction from logical runs.
  - Prevent an extra final summary history record from duplicating attempt tokens. Preserve nullable unknown usage; cover success, exhaustion, successor-auth failure, cancellation and timeout.
  - Coordinate the history shape with the headless model slice; extend existing additive JSON conventions and retain readability of old history.
- Out:
  - No unrelated refactor, new service, or live provider/credential operation.

# Acceptance criteria
- AC1: Synthetic A=100 input/10 output then B=200/20 yields A=100/10 and B=200/20, aggregate 300/30, one logical run, and no duplicate final usage.
- AC2: Failed earlier attempts retain durations and terminal outcomes even if a later attempt cannot start.
- AC3: Existing non-failover and registry occupancy contracts stay intact.

# AC Traceability
- request-AC3 -> This backlog slice. Proof: Implemented in `0b34fb3`; `test_failover_continues_the_task_on_the_next_account` passed in the 1076-test Python suite. See Implementation evidence below.
- request-AC11 -> This backlog slice. Proof: Implemented in `0b34fb3`; `test_failover_continues_the_task_on_the_next_account` passed in the 1076-test Python suite. See Implementation evidence below.
- request-AC12 -> This backlog slice. Proof: Implemented in `0b34fb3`; `test_failover_continues_the_task_on_the_next_account` passed in the 1076-test Python suite. See Implementation evidence below.

> Shared proof: AC3, AC11, AC12

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
- Rationale: correct session attribution and missing consumption before refining presentation.

# Implementation entry points
- src/commands/runs.py, src/session_service.py, src/run_registry.py and src/commands/status.py.

# Dependencies and sequencing
- After the High-priority wave; agree history attempt semantics before item_161 and item_162.

# Validation plan
- Start with `node bin/python-runner.js -m pytest -q test/test_commands_runs_py.py test/test_run_failover_py.py test/test_commands_status_py.py`.
- Add the smallest regression that fails on the reviewed defect; these existing suites alone are not proof of the fix.
- Finish with repository lint and the orchestration task cross-slice validation. Keep all fixture data synthetic and temporary.

# Implementation evidence
- Each blocking headless attempt writes one history row with its actual session, run ID, attempt number, outcome, duration and usage before failover advances. The registry remains one logical run. Provider launch exceptions with run information also write one failed attempt.
- `test_failover_continues_the_task_on_the_next_account` verifies A=100/10 and B=200/20 in separate session histories with one shared run ID and registry entry.
- The same regression aggregates both histories to 300 input and 30 output tokens, two launch attempts and two priced model observations.

# Tasks
- `task_085_orchestrate_review_hardening_across_persistence_stats_and_handoff`

# Notes
- Task `task_085_orchestrate_review_hardening_across_persistence_stats_and_handoff` was finished via `logics-manager flow finish task` on 2026-10-04.
