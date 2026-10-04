## item_157_serialize_memory_appends_across_independent_cli_processes - Serialize memory appends across independent CLI processes
> From version: 0.20.14
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 95%
> Complexity: Medium
> Theme: Memory integrity
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-10-04 17:17:36

# AI Context
- Summary: req_077 finding 2: process-local threading locks allow two successful CLI writers to replace one another's notes.
- Keywords: serialize, memory, appends, across, independent, cli, processes
- Use when: Implementing serialize memory appends across independent cli processes.
- Skip when: Working outside this slice or adding deferred worktree management.

# Problem
- req_077 finding 2: process-local threading locks allow two successful CLI writers to replace one another's notes.

# Scope
- In:
  - Use a stable per-memory-file filesystem lock across the read-modify-write sequence, covering current, named-project and global scopes on supported platforms.
  - Reuse a suitable existing locking primitive if its semantics fit; bound lock acquisition, release on process exit, and never lock only the replaced data-file inode.
  - Test real independent processes with controlled overlap and unique notes; retain the existing thread regression. Synchronization must not deadlock a corrected serialized reader.
- Out:
  - No unrelated refactor, new service, or live provider/credential operation.

# Acceptance criteria
- AC1: At least two successful independent appends preserve initial text and all accepted notes exactly once.
- AC2: Lock timeout or write failure returns an actionable error without reporting success or corrupting existing content.
- AC3: POSIX and Windows locking paths are covered by platform-appropriate checks; no timing-only flaky assertion.

# AC Traceability
- request-AC2 -> This backlog slice. Proof deferred to implementation closeout; record the concrete regression and command result.
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
- Rationale: prevent silent loss of accepted user or agent notes before lower-priority reporting work.

# Implementation entry points
- src/context_store.py and the existing lock implementations in src/session_store.py / src/run_registry.py.

# Dependencies and sequencing
- None; execute after the import slice to complete the High-priority wave.

# Validation plan
- Start with `node bin/python-runner.js -m pytest -q test/test_context_store_py.py test/test_commands_context_memory_py.py`.
- Add the smallest regression that fails on the reviewed defect; these existing suites alone are not proof of the fix.
- Finish with repository lint and the orchestration task cross-slice validation. Keep all fixture data synthetic and temporary.

# Implementation evidence
- Memory appends now hold a stable sidecar file lock across read, modify and atomic replacement. The existing registry lock primitive supplies bounded POSIX and Windows acquisition; a thread lock continues to serialize same-process writers.
- Regressions: `test_independent_processes_keep_every_accepted_note` uses two child processes, and `test_append_lock_failure_never_reports_success_or_changes_memory` checks the failure boundary.
- Wave 1 focused run: `node bin/python-runner.js -m pytest -q test/test_context_store_py.py test/test_commands_context_memory_py.py test/test_run_registry_py.py test/test_profile_data_safety_py.py test/test_commands_backup_py.py` — 68 passed. Native Windows execution remains for platform validation.
