## item_139_smoke_test_doctor_from_packed_npm_and_wheel_artifacts - Smoke test doctor from packed npm and wheel artifacts
> From version: 0.20.4
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Low
> Theme: Release verification
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-22 11:59:10

# AI Context
- Summary: Test the operational doctor command after installation from each package artifact.
- Keywords: smoke, test, doctor, packed, npm, wheel, artifacts
- Use when: Adding deterministic release smoke coverage for packaged CDX commands.
- Skip when: Calling a provider service, publishing a package, or expanding the OS matrix.

# Problem
- Package jobs validate only command metadata, so a packaged operational doctor regression can escape the source test matrix.

# Scope
- In:
  - Extend the existing package-smoke job with controlled command shims and isolated CDX state.
  - Run doctor from both installed package forms.
- Out:
  - Live account checks, package publication, or an additional CI platform matrix.

# Acceptance criteria
- AC1: The packed npm installation runs `cdx doctor --json` against the local shims.
- AC2: The wheel installation runs the same smoke against the local shims.
- AC3: The job stays deterministic without network or credential access.

# AC Traceability
- request-AC3 -> This backlog slice. Proof: AC1: The packed npm installation runs `cdx doctor --json` against the local shims.
- request-AC4 -> This backlog slice. Proof: AC2: The wheel installation runs the same smoke against the local shims.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_052_reliable_codex_diagnostics_in_packaged_installs`
- Architecture decision(s): (none yet)
- Request: `req_069_harden_codex_probe_process_and_package_smoke_coverage`
- Primary task(s): `task_078_orchestrate_reliable_codex_diagnostics_and_package_smokes`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
