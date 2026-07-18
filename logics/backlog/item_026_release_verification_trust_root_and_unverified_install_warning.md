## item_026_release_verification_trust_root_and_unverified_install_warning - Release verification trust root and unverified-install warning
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
- install.sh/install.ps1 fetch release checksums from the same main branch as the artifact, so one repository compromise updates both; CDX_ALLOW_UNVERIFIED=1 silently disables verification.

# Scope
- In:
  - Publish per-release checksums as tagged GitHub Release assets and point both installers at the release asset for verification.
  - Print a prominent multi-line warning when CDX_ALLOW_UNVERIFIED is set.
  - Update the release checklist/scripts so publishing the checksum asset is part of the release flow.
- Out:
  - Sigstore/GPG signing.

# Acceptance criteria
- Installers verify archives against the tagged release asset, not main-branch files.
- Setting CDX_ALLOW_UNVERIFIED produces an unmissable warning before proceeding.
- Release verification scripts and their tests stay green.

# AC Traceability
- request-AC11 -> This backlog slice. Proof: Installers verify archives against the tagged release asset, not main-branch files.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_003_code_review_remediation_wave_2026_07`
- Architecture decision(s): (none yet)
- Request: `req_010_address_july_2026_code_review_findings_data_safety_reliability_and_cleanup`
- Primary task(s): `task_021_orchestrate_july_2026_code_review_remediation`

# AI Context
- Summary: Release verification trust root and unverified-install warning
- Keywords: scaffolded-backlog, release verification trust root and unverified-install warning, implementation-ready
- Use when: Implementing the scaffolded slice for Release verification trust root and unverified-install warning.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
