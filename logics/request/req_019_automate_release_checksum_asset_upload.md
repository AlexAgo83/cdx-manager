## req_019_automate_release_checksum_asset_upload - Automate release checksum asset upload
> From version: 0.12.2
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Release governance
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# Needs
- Release publication must automatically attach `checksums/release-archives.json` to the matching GitHub Release so `cdx update` can verify official archives immediately.
- Maintainers should not have to remember a manual `gh release upload <tag> checksums/release-archives.json` step after publishing.
- The release process should fail closed when checksum generation or upload fails, before users encounter a broken update path.

# Context
- GitHub issue #4 reports that `v0.12.2` was tagged, pushed, and released on 2026-08-05 without the `release-archives.json` release asset.
- `cdx update` then refused to install with `cdx install: no official checksum available for v0.12.2`, which is correct verification behavior but a bad release workflow outcome.
- Existing related docs are Done and adjacent: `item_013_release_checksum_governance_gate` validates local checksum metadata before publication, `item_026_release_verification_trust_root_and_unverified_install_warning` moved installer trust to release assets, and `item_028_use_tagged_release_checksum_assets_in_package_publication_workflows` makes package publication consume tagged release assets.
- This request is the earlier gap: ensuring the release asset exists and is uploaded automatically.

# Acceptance criteria
- AC1: A GitHub Actions workflow or release automation path generates `checksums/release-archives.json` for the released tag.
- AC2: The automation uploads or replaces the `release-archives.json` asset on the matching GitHub Release.
- AC3: The workflow has the minimum permissions needed to read repository contents and write release assets.
- AC4: Failures in checksum generation or asset upload fail the workflow visibly and leave an actionable log.
- AC5: Tests or workflow linters verify the trigger, tag wiring, checksum command, upload target, and permissions.
- AC6: README/release maintainer notes no longer rely on a purely manual post-release upload step; they describe the automated path and any manual repair command.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# References
- GitHub issue #4
- `.github/workflows/`
- `scripts/update_release_checksums.py`
- `checksums/release-archives.json`
- `scripts/verify_release_checksums.py`
- `test/test_release_checksums_py.py`
- `test/test_release_ci_py.py`
- Existing adjacent corpus: `item_013_release_checksum_governance_gate`, `item_026_release_verification_trust_root_and_unverified_install_warning`, `item_028_use_tagged_release_checksum_assets_in_package_publication_workflows`

# AI Context
- Summary: Automate upload of per-release checksum metadata to GitHub Releases.
- Keywords: GitHub issue #4, release-archives.json, gh release upload, GitHub Actions, release published, checksum asset, cdx update
- Use when: Implementing or reviewing release automation that attaches checksum assets.
- Skip when: Work is only about installer checksum verification or package workflows consuming an already uploaded asset.

# Backlog
- none
- `item_039_automate_release_checksum_asset_upload`
