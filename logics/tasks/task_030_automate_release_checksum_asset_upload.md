## task_030_automate_release_checksum_asset_upload - Automate release checksum asset upload
> From version: 0.12.2
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# Definition of Done (DoD)
- [ ] The backlog scope is implemented.
- [ ] Acceptance criteria are covered.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# Backlog
- `item_039_automate_release_checksum_asset_upload`

# Acceptance criteria
- AC1: A workflow triggered by `release: published`, tag push, or an explicitly documented release automation event computes checksums for the released tag.
- AC2: The workflow uploads `checksums/release-archives.json` to `releases/download/<tag>/release-archives.json` or the equivalent GitHub Release asset endpoint.
- AC3: The workflow declares `contents: write` only where needed and does not require broad secrets beyond the standard GitHub token unless documented.
- AC4: Rerunning the workflow is idempotent or has a documented safe replacement behavior for an existing checksum asset.
- AC5: Static tests inspect the workflow for trigger, tag/ref propagation, checksum script invocation, release upload target, and permissions.
- AC6: Release documentation says the asset upload is automated and gives `gh release upload <tag> checksums/release-archives.json --clobber` or equivalent as the manual repair command.
- AC7: Existing release checksum validation tests remain green.

# Plan
- [ ] 1. Inspect current release workflows, release scripts, README maintainer notes, and checksum tests.
- [ ] 2. Add the smallest GitHub Actions workflow or release step that derives the tag from the release event and runs `scripts/update_release_checksums.py --tag <tag>`.
- [ ] 3. Upload `checksums/release-archives.json` to the matching GitHub Release with safe rerun behavior.
- [ ] 4. Add or update static workflow tests for trigger, permissions, tag propagation, checksum generation, and upload target.
- [ ] 5. Update release docs to remove reliance on memory and include the manual repair command.
- [ ] 6. Run focused release checksum/workflow tests plus Logics lint.

# Validation
- Planned: focused release checksum and workflow static tests.
- Planned: `logics-manager lint --require-status`.

# Report
- Not started.

# AI Context
- Summary: Implement automated GitHub Release upload for checksum metadata.
- Keywords: GitHub issue #4, release-archives.json, GitHub Actions, gh release upload, release published, checksum asset
- Use when: Implementing the task for automated release checksum asset upload.
- Skip when: Work is about `cdx run` validation or run registry persistence.

# Links
- Request: `req_019_automate_release_checksum_asset_upload`
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# AC Traceability
- request-AC1 -> Task AC1. Proof: automation computes checksums for the release tag.
- request-AC2 -> Task AC2, Task AC4. Proof: automation uploads or safely replaces the matching release asset.
- request-AC3 -> Task AC3. Proof: permissions are explicit and minimal.
- request-AC4 -> Task AC5. Proof: workflow tests enforce visible automation behavior.
- request-AC5 -> Task AC5. Proof: static checks cover trigger, tag wiring, command, target, and permissions.
- request-AC6 -> Task AC6. Proof: release docs describe automation and manual repair.
