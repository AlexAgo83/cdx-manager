## item_029_fix_standalone_windows_installer_launcher_generation - Fix standalone Windows installer launcher generation
> From version: 0.10.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Low
> Theme: Operator workflow
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- install.ps1 writes a here-string containing `${($tag.TrimStart("v"))}`, which PowerShell does not evaluate as intended.
- The generated cdx.cmd launcher omits the version directory and points at a non-existent script path.

# Scope
- In:
  - Compute the version directory in a normal PowerShell variable before building the here-string.
  - Use that variable in the generated `SCRIPT` path so the launcher points at the installed version.
  - Add a regression test that evaluates or statically verifies the generated launcher content for a sample tag.
- Out:
  - Changing the Windows installer destination layout.
  - Changing npm launcher behavior.

# Acceptance criteria
- For tag `v1.2.3`, the generated launcher path includes `versions\1.2.3\bin\cdx`.
- The installer no longer contains `${($tag.TrimStart("v"))}` inside the generated batch script.
- The regression test fails on the previous empty-version launcher output.

# AC Traceability
- request-AC2 -> This backlog slice. Proof: For tag `v1.2.3`, the generated launcher path includes `versions\1.2.3\bin\cdx`.
- request-AC5 -> This backlog slice. Proof: The installer no longer contains `${($tag.TrimStart("v"))}` inside the generated batch script.
- request-AC1 -> This backlog slice. Evidence needed: npm and PyPI publish workflows validate release checksums against the tagged GitHub Release asset for the release tag, not against a main-branch checksum file.
- request-AC3 -> This backlog slice. Evidence needed: Provider auth probe timeouts surface as unknown/degraded probe results, not logged-out results; launch/run/status/doctor callers handle that state explicitly without persisting a false logout.
- request-AC4 -> This backlog slice. Evidence needed: Import bundle profile validation rejects non-object profile entries with `CdxError` before any filesystem mutation, and tests cover the malformed-entry case.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_004_post_remediation_hardening_follow_up_2026_07`
- Architecture decision(s): (none yet)
- Request: `req_011_address_july_2026_post_remediation_review_follow_up_findings`
- Primary task(s): `task_022_orchestrate_post_remediation_hardening_follow_up`

# AI Context
- Summary: Fix standalone Windows installer launcher generation
- Keywords: scaffolded-backlog, fix standalone windows installer launcher generation, implementation-ready
- Use when: Implementing the scaffolded slice for Fix standalone Windows installer launcher generation.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.

# Tasks
- `task_022_orchestrate_post_remediation_hardening_follow_up`

# Notes
- Task `task_022_orchestrate_post_remediation_hardening_follow_up` was finished via `logics-manager flow finish task` on 2026-07-18.
