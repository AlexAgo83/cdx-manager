## item_124_restore_contributor_and_logics_workflow_signal_accuracy - Restore contributor and Logics workflow signal accuracy
> From version: 0.19.1
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Low
> Theme: Workflow hygiene
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-13 22:09:18

# AI Context
- Summary: Keep contributor validation instructions and terminal Logics progress trustworthy.
- Keywords: contribution guide, validation commands, historical progress, completion metadata
- Use when: Updating contributor workflow documentation or historical completion metadata.
- Skip when: Reprioritising or reopening completed product work.

# Problem
- CONTRIBUTING.md references test/test_cli_py.py, which no longer exists.
- Workflow health reports completed backlog records whose progress remains below 100%.

# Scope
- In:
  - Update contributor validation guidance to current command-module tests and tray checks.
  - Reconcile the identified Done backlog progress records through the supported Logics lifecycle operations.
  - Validate the updated documentation and workflow health signal.
- Out:
  - Rewriting all historical release documentation.
  - Changing product priority or reopening completed work.

# Acceptance criteria
- Contributor documentation names only existing test paths and required validation commands.
- The identified Done workflow records have consistent terminal progress.
- Logics lint and scoped health/audit checks pass for the changed records.

# AC Traceability
- request-AC9 -> This backlog slice. Proof: Contributor documentation names only existing test paths and required validation commands.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_047_reliable_delivery_and_runtime_contracts`
- Architecture decision(s): (none yet)
- Request: `req_061_harden_repository_reliability_release_verification_and_cli_contracts`
- Primary task(s): `task_071_orchestrate_repository_reliability_and_release_contract_hardening`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.

# Tasks
- `task_071_orchestrate_repository_reliability_and_release_contract_hardening`

# Notes
- Task `task_071_orchestrate_repository_reliability_and_release_contract_hardening` was finished via `logics-manager flow finish task` on 2026-08-13.
