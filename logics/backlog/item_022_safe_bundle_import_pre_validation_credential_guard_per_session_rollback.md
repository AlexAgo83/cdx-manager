## item_022_safe_bundle_import_pre_validation_credential_guard_per_session_rollback - Safe bundle import: pre-validation, credential guard, per-session rollback
> From version: 0.10.0
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Operator workflow
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- import --force removes each existing session profile before re-import; a bundle exported without --include-auth restores no credentials, so every overwritten session is permanently logged out.
- Bundle content is validated mid-loop after destructive writes have begun, so a corrupt entry leaves earlier sessions committed, the failing session half-deleted, and later sessions untouched.

# Scope
- In:
  - Refuse --force import over existing sessions when the bundle carries no auth payloads, unless an explicit override flag is passed.
  - Validate all base64 payloads and target paths for a session before any filesystem mutation.
  - Rename the existing profile aside during import, restore it if the import of that session fails, delete the backup on success (reuse the existing quarantine pattern from remove_session).
  - Round-trip tests: force-import without auth is refused; corrupt mid-bundle entry leaves the pre-import profile intact.
- Out:
  - Bundle format changes or new export options.

# Acceptance criteria
- Force-importing an auth-less bundle over existing sessions exits with an explicit refusal message and touches nothing.
- A corrupt payload in session N leaves session N's original profile and store record intact.
- Existing export/import round-trip tests remain green.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: Force-importing an auth-less bundle over existing sessions exits with an explicit refusal message and touches nothing.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_003_code_review_remediation_wave_2026_07`
- Architecture decision(s): (none yet)
- Request: `req_010_address_july_2026_code_review_findings_data_safety_reliability_and_cleanup`
- Primary task(s): `task_021_orchestrate_july_2026_code_review_remediation`

# AI Context
- Summary: Safe bundle import: pre-validation, credential guard, per-session rollback
- Keywords: scaffolded-backlog, safe bundle import: pre-validation, credential guard, per-session rollback, implementation-ready
- Use when: Implementing the scaffolded slice for Safe bundle import: pre-validation, credential guard, per-session rollback.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
