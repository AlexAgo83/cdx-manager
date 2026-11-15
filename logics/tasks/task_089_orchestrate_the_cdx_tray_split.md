## task_089_orchestrate_the_cdx_tray_split - Orchestrate the cdx-tray split
> From version: 0.27.12
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-11-15 02:31:50

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: orchestrate, cdx, tray, split
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Contract first (item 1), released in a cdx version so cdx-tray can rely on it.
- [x] 2. Create cdx-tray (item 2) and publish its first release built from the same sources.
- [x] 3. Switch `cdx tray install` (item 3), then remove the tray from cdx-manager (item 4) in the next cdx release.
- [x] 4. Verify on a real machine: install, launch, menu refresh, and a cdx release that publishes without tray jobs.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_172_version_the_tray_contract_and_pin_its_json_shape`
- `item_173_create_the_public_cdx_tray_repository_with_its_ci_and_releases`
- `item_174_install_the_tray_from_cdx_tray_releases`
- `item_175_remove_the_tray_from_cdx_manager_and_announce_contract_changes`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_172_version_the_tray_contract_and_pin_its_json_shape`. Proof: src/tray_contract.py keeps schema name/major/minor; test/test_tray_contract_shape_py.py (test_the_current_schema_version_has_a_recorded_shape_that_matches, test_minor_versions_only_add_keys) pins test/fixtures/tray_contract_shapes.json.
- request-AC2 -> `item_173_create_the_public_cdx_tray_repository_with_its_ci_and_releases`. Proof: AlexAgo83/cdx-tray ci.yml and release.yml build and test the five targets; release v0.17.1 ships them with release-archives.json (checksums/release-archives.json, commit f852160); contract.yml checks the CDX snapshot major daily and fails when CDX moves on.
- request-AC5 -> `item_173_create_the_public_cdx_tray_repository_with_its_ci_and_releases`. Proof: cdx-tray src/snapshot.rs read_snapshot keeps rendering a newer major with an update_hint ("Update the tray companion."), test a_newer_major_still_renders_with_a_hint.
- request-AC3 -> `item_174_install_the_tray_from_cdx_tray_releases`. Proof: src/tray_install.py tray_release picks the newest cdx-tray release whose ledger schema_major matches and raises an update message otherwise; expected_checksum verifies against the ledger; test/test_tray_capability_py.py test_installs_the_newest_compatible_cdx_tray_release, test_refuses_when_no_cdx_tray_release_reads_this_major.
- request-AC4 -> `item_175_remove_the_tray_from_cdx_manager_and_announce_contract_changes`. Proof: commit 34b0c4c (released in v0.27.13) removes tray/ and the tray asset workflow; PR #149 (4728242) makes upload-release-checksums.yml attach the ledger without tray jobs; v0.27.13 has no tray assets while v0.27.12 keeps its 5.

# Validation
- (no validation recorded yet)
- nice -n 19 python3 -m pytest -q test/test_tray_contract_shape_py.py test/test_tray_contract_py.py test/test_tray_commands_py.py test/test_tray_capability_py.py passed on 2026-11-15: 118 passed
- cdx-tray CI, CDX contract and Build tray companion assets workflows green on main (a24226d, 973ecda); release v0.17.1 carries 5 assets and release-archives.json, checked on 2026-11-15
- Finish workflow executed on 2026-11-15.
- Linked backlog/request close verification passed.
- nice -n 19 cargo test a_newer_major in cdx-tray passed on 2026-11-15: 1 passed

# Report
- Not started.
- Finished on 2026-11-15.
- Linked backlog item(s): `item_172_version_the_tray_contract_and_pin_its_json_shape`, `item_173_create_the_public_cdx_tray_repository_with_its_ci_and_releases`, `item_174_install_the_tray_from_cdx_tray_releases`, `item_175_remove_the_tray_from_cdx_manager_and_announce_contract_changes`
- Related request(s): `req_085_move_the_tray_companion_into_its_own_cdx_tray_repository`

# Links
- Request: `req_085_move_the_tray_companion_into_its_own_cdx_tray_repository`
- Product brief(s): `prod_059_cdx_tray_the_tray_companion_released_on_its_own`
- Architecture decision(s): (none yet)

# Executions
| When | Runner | Run id | Title | State | PR | Notes |
| --- | --- | --- | --- | --- | --- | --- |
