## item_136_exclude_disabled_profiles_from_bulk_codex_refresh - Exclude disabled profiles from bulk Codex refresh
> From version: 0.20.4
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Low
> Theme: Authentication reliability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-22 12:01:27

# AI Context
- Summary: Keep intentionally disabled profiles out of bulk checks while retaining explicit diagnostic access.
- Keywords: exclude, disabled, profiles, bulk, codex, refresh
- Use when: Bulk refresh should operate only on eligible Codex profiles.
- Skip when: Automatically changing profile state or deleting profile data.

# Problem
- A disabled profile still participates in bulk authentication refresh and can create a known false alert.

# Scope
- In:
  - Filter disabled sessions only for the bulk target.
  - Keep explicit named probing unchanged and document the distinction.
- Out:
  - Deleting sessions automatically or changing their enabled state.

# Acceptance criteria
- AC1: Bulk refresh omits disabled Codex sessions.
- AC2: An explicit disabled session remains probeable by name.
- AC3: JSON and text tests prove the selection behavior.

# AC Traceability
- request-AC2 -> This backlog slice. Proof: AC1: Bulk refresh omits disabled Codex sessions.
- request-AC4 -> This backlog slice. Proof: AC2: An explicit disabled session remains probeable by name.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_051_truthful_codex_authentication_health_signals`
- Architecture decision(s): (none yet)
- Request: `req_068_harden_codex_authentication_observability`
- Primary task(s): `task_077_orchestrate_truthful_codex_authentication_health_signals`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
