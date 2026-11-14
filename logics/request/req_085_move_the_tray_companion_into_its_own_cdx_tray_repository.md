## req_085_move_the_tray_companion_into_its_own_cdx_tray_repository - Move the tray companion into its own cdx-tray repository
> From version: 0.27.12
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Tray companion
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-11-14 15:01:07

# AI Context
- Summary: Split the Rust tray companion into the public cdx-tray repository with a versioned `cdx tray status --json` contract, so cdx releases stop rebuilding and waiting for tray assets.
- Keywords: cdx-tray, tray companion, contract version, tray install, release workflow, repository_dispatch
- Use when: changing the tray, its JSON contract, `cdx tray install`, or the release workflows that build tray assets.
- Skip when: cdx features that do not touch the tray status contract or tray installation.

# Needs
- The tray companion (Rust, tray/) lives in its own public repository, cdx-tray, with its own CI and releases.
- A cdx release no longer rebuilds the tray assets nor waits for them before publishing to npm and PyPI.
- The tray CI and releases only run when the tray changes or when cdx publishes a breaking change of the tray contract.

# Context
- Maintainer decision (2026-11-14): repository name cdx-tray; implemented directly, not delegated.
- Today the tray only talks to cdx through `cdx tray status --json`; it imports no cdx code. Every cdx release rebuilds every tray target (about 3 minutes) and the npm/PyPI publish jobs wait for that build, even when the tray did not change.
- `cdx tray install` downloads `cdx-tray-{version}-{target}.tar.gz` from the cdx release of the same version and verifies it against the release-archives.json checksum ledger. After the move it must pick the newest cdx-tray release that supports the installed cdx schema major.
- cdx-tray is public: copy clean files without importing this repository's history, and keep every value generic (no host, account or path specific to one installation).

# Acceptance criteria
- AC1: `cdx tray status --json` keeps its existing `schema` (name, major, minor); a test pins the JSON shape per version, so a change fails until the minor (added keys) or major (removed or renamed keys) is bumped.
- AC2: The public cdx-tray repository builds, tests and releases the tray assets with their checksum ledger, on its own changes or when cdx announces a new schema major.
- AC3: `cdx tray install` installs the newest cdx-tray release that supports the installed contract, verified against that release's checksum ledger; an unsupported contract is refused with a clear update message.
- AC4: cdx-manager no longer contains tray/ nor the tray asset workflow; its publish jobs no longer wait for tray assets; earlier cdx releases keep their published tray assets.
- AC5: The tray shows an update message instead of failing when cdx reports a contract it does not know.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_059_cdx_tray_the_tray_companion_released_on_its_own`
- Architecture decision(s): (none yet)

# References
- tray/Cargo.toml
- tray/src/snapshot.rs
- src/tray_install.py
- src/cli_commands.py
- .github/workflows/build-tray-assets.yml
- .github/workflows/publish-npm.yml
- .github/workflows/publish-pypi.yml
- checksums/release-archives.json
- docs/tray-local-testing.md

# Backlog
- `item_172_version_the_tray_contract_and_pin_its_json_shape`
- `item_173_create_the_public_cdx_tray_repository_with_its_ci_and_releases`
- `item_174_install_the_tray_from_cdx_tray_releases`
- `item_175_remove_the_tray_from_cdx_manager_and_announce_contract_changes`

# Executions
| When | Runner | Run id | Title | State | PR | Notes |
| --- | --- | --- | --- | --- | --- | --- |
