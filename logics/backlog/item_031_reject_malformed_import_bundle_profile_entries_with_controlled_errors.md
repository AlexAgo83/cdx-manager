## item_031_reject_malformed_import_bundle_profile_entries_with_controlled_errors - Reject malformed import bundle profile entries with controlled errors
> From version: 0.10.0
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Low
> Theme: Operator workflow
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- Bundle profile validation calls `.get()` on profile entries before checking their type.
- A malformed profile entry raises a raw `AttributeError` instead of a controlled `CdxError`.

# Scope
- In:
  - Validate that each profile entry is an object before reading `path` or `data_b64`.
  - Raise a clear `CdxError` for non-object entries, missing paths, unsafe paths, or invalid base64.
  - Add regression tests proving malformed entries fail before session profile mutation.
- Out:
  - Changing the bundle schema version.
  - Changing encrypted bundle serialization.

# Acceptance criteria
- A bundle with `profiles: {"main": [null]}` raises `CdxError` with a bundle-validation message.
- Existing credentials and session records remain intact after that failure.
- Existing import/export round-trip tests remain green.

# AC Traceability
- request-AC4 -> This backlog slice. Proof: A bundle with `profiles: {"main": [null]}` raises `CdxError` with a bundle-validation message.
- request-AC5 -> This backlog slice. Proof: Existing credentials and session records remain intact after that failure.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_004_post_remediation_hardening_follow_up_2026_07`
- Architecture decision(s): (none yet)
- Request: `req_011_address_july_2026_post_remediation_review_follow_up_findings`
- Primary task(s): `task_022_orchestrate_post_remediation_hardening_follow_up`

# AI Context
- Summary: Reject malformed import bundle profile entries with controlled errors
- Keywords: scaffolded-backlog, reject malformed import bundle profile entries with controlled errors, implementation-ready
- Use when: Implementing the scaffolded slice for Reject malformed import bundle profile entries with controlled errors.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
