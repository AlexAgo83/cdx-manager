## item_039_automate_release_checksum_asset_upload - Automate release checksum asset upload
> From version: 0.12.2
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: High
> Theme: Operator workflow and runtime integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- The release process can publish a GitHub Release without the `release-archives.json` asset required by verified installers.
- This makes `cdx update` fail for the released version until someone notices and runs a manual upload command.
- Prior checksum hardening correctly fails closed, but the release workflow still lacks an automated asset publication gate.

# Scope
- In:
  - Add a GitHub Actions workflow or equivalent release automation that runs for the published release/tag path.
  - Generate or refresh `checksums/release-archives.json` for the release tag using the existing checksum script.
  - Upload the checksum file as a GitHub Release asset for the same tag, replacing an older asset when rerun if supported by the chosen tool.
  - Add tests or static checks that prevent regressions in trigger, permissions, tag wiring, and upload command.
  - Update release docs with automated behavior and a manual repair command.
- Out:
  - Changing the checksum JSON schema.
  - Changing installer trust policy or allowing unverified installs by default.
  - Reworking npm/PyPI publication workflow checksum consumption beyond ensuring their dependency asset exists.

# Acceptance criteria
- AC1: A workflow triggered by `release: published`, tag push, or an explicitly documented release automation event computes checksums for the released tag.
- AC2: The workflow uploads `checksums/release-archives.json` to `releases/download/<tag>/release-archives.json` or the equivalent GitHub Release asset endpoint.
- AC3: The workflow declares `contents: write` only where needed and does not require broad secrets beyond the standard GitHub token unless documented.
- AC4: Rerunning the workflow is idempotent or has a documented safe replacement behavior for an existing checksum asset.
- AC5: Static tests inspect the workflow for trigger, tag/ref propagation, checksum script invocation, release upload target, and permissions.
- AC6: Release documentation says the asset upload is automated and gives `gh release upload <tag> checksums/release-archives.json --clobber` or equivalent as the manual repair command.
- AC7: Existing release checksum validation tests remain green.

# AC Traceability
- request-AC1 -> AC1. Proof: Workflow computes checksums for the released tag.
- request-AC2 -> AC2, AC4. Proof: Workflow uploads/replaces the release asset for that tag.
- request-AC3 -> AC3. Proof: Permissions are explicit and minimal.
- request-AC4 -> AC5. Proof: Tests check failure-visible automation wiring.
- request-AC5 -> AC5. Proof: Static workflow tests cover trigger, command, target, and permissions.
- request-AC6 -> AC6. Proof: Release docs describe automation and manual repair.

# Decision framing
- Product framing: Not needed
- Product signals: (none detected)
- Product follow-up: No product brief follow-up is expected based on current signals.
- Architecture framing: Not needed
- Architecture signals: (none detected)
- Architecture follow-up: No architecture decision follow-up is expected based on current signals.

# Links
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
- Request: `req_019_automate_release_checksum_asset_upload`
- Primary task(s): `task_030_automate_release_checksum_asset_upload`

# AI Context
- Summary: Add release automation that attaches `release-archives.json` to every GitHub Release.
- Keywords: GitHub issue #4, release-archives.json, GitHub Actions, release published, gh release upload, checksum asset
- Use when: Implementing the release checksum asset upload workflow.
- Skip when: The change only validates local checksum metadata or installer download behavior.

# Priority
- Priority: High
- Rationale: A missing checksum asset breaks verified updates for every released version until manual repair.

# Notes
- Hybrid rationale: Derived from request `req_019_automate_release_checksum_asset_upload` and kept bounded to one coherent delivery slice.
- Source file: `logics/request/req_019_automate_release_checksum_asset_upload.md`.
- Generated locally by logics-manager.
- Related existing corpus is Done and adjacent: `item_013_release_checksum_governance_gate`, `item_026_release_verification_trust_root_and_unverified_install_warning`, `item_028_use_tagged_release_checksum_assets_in_package_publication_workflows`.
- Task `task_030_automate_release_checksum_asset_upload` was finished via `logics-manager flow finish task` on 2026-08-05.

# Tasks
- `task_030_automate_release_checksum_asset_upload`
