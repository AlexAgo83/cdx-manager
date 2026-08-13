## item_120_verify_installable_package_artifacts_before_release - Verify installable package artifacts before release
> From version: 0.19.1
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 20%
> Complexity: Medium
> Theme: Release integrity
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-13 22:09:01

# AI Context
- Summary: Verify that npm and wheel artifacts can be installed and invoked before release publication.
- Keywords: verify, installable, package, artifacts, before, release
- Use when: Changing package CI, release gates, or workflow action references.
- Skip when: Designing a new artifact-signing system.

# Problem
- Pre-release CI only dry-runs npm packing and does not install a built npm or wheel artifact.
- Release workflows with write permissions use mutable third-party action tags.

# Scope
- In:
  - Build npm and Python artifacts in CI before release publication.
  - Install each artifact into a clean temporary environment and execute a minimal CLI smoke test with provider shims.
  - Pin GitHub Action references to immutable revisions and retain readable version comments or automated update support.
- Out:
  - Publishing from pull requests.
  - Introducing a new artifact signing system.

# Acceptance criteria
- CI installs and invokes the packed npm artifact before a release can publish.
- CI builds, checks, installs, and invokes the wheel before a release can publish.
- Release workflow actions are pinned to immutable revisions without expanding permissions.

# AC Traceability
- request-AC2 -> This backlog slice. Proof: CI installs and invokes the packed npm artifact before a release can publish.
- request-AC3 -> This backlog slice. Proof: CI builds, checks, installs, and invokes the wheel before a release can publish.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_047_reliable_delivery_and_runtime_contracts`
- Architecture decision(s): (none yet)
- Request: `req_061_harden_repository_reliability_release_verification_and_cli_contracts`
- Primary task(s): `task_071_orchestrate_repository_reliability_and_release_contract_hardening`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
