## item_028_use_tagged_release_checksum_assets_in_package_publication_workflows - Use tagged release checksum assets in package publication workflows
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
- The npm and PyPI publish workflows still download checksum metadata from the repository main branch.
- This leaves package publication with the mutable-main trust root that the installer hardening was meant to remove.

# Scope
- In:
  - Change both publish workflows to download `release-archives.json` from the tagged GitHub Release asset for `RELEASE_TAG`.
  - Keep the existing release checksum validator as the package-publish gate.
  - Add or update tests that detect any workflow fallback to main-branch checksum metadata.
- Out:
  - Signing release archives or package artifacts.
  - Changing how checksum files are generated.

# Acceptance criteria
- The publish workflows contain no raw.githubusercontent.com main-branch checksum URL.
- The publish workflows validate checksums from `releases/download/$RELEASE_TAG/release-archives.json` or an equivalent tagged-release asset URL.
- Release checksum tests fail if package publication reintroduces a main-branch checksum trust root.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: The publish workflows contain no raw.githubusercontent.com main-branch checksum URL.
- request-AC5 -> This backlog slice. Proof: The publish workflows validate checksums from `releases/download/$RELEASE_TAG/release-archives.json` or an equivalent tagged-release asset URL.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_004_post_remediation_hardening_follow_up_2026_07`
- Architecture decision(s): (none yet)
- Request: `req_011_address_july_2026_post_remediation_review_follow_up_findings`
- Primary task(s): `task_022_orchestrate_post_remediation_hardening_follow_up`

# AI Context
- Summary: Use tagged release checksum assets in package publication workflows
- Keywords: scaffolded-backlog, use tagged release checksum assets in package publication workflows, implementation-ready
- Use when: Implementing the scaffolded slice for Use tagged release checksum assets in package publication workflows.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
