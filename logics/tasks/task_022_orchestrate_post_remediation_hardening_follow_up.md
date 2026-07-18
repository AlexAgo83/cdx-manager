## task_022_orchestrate_post_remediation_hardening_follow_up - Orchestrate post-remediation hardening follow-up
> From version: 0.10.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Owner: codex

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Fix the release publication trust root first because it affects package integrity.
- [x] 2. Fix and test the Windows installer launcher generation.
- [x] 3. Introduce explicit auth probe timeout/degraded semantics and migrate callers.
- [x] 4. Harden bundle profile entry validation and add the malformed-entry regression.
- [x] 5. Update docs and Logics reports during closeout, then run the full validation suite.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_028_use_tagged_release_checksum_assets_in_package_publication_workflows`
- `item_029_fix_standalone_windows_installer_launcher_generation`
- `item_030_preserve_degraded_auth_semantics_on_provider_probe_timeout`
- `item_031_reject_malformed_import_bundle_profile_entries_with_controlled_errors`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: `.github/workflows/publish-npm.yml` and `.github/workflows/publish-pypi.yml` now fetch `release-archives.json` from `releases/download/${RELEASE_TAG}`; `test_release_checksums_py.py` rejects main-branch checksum URLs.
- request-AC2 -> This task. Proof: `install.ps1` computes `$versionDir` before launcher generation and writes `set SCRIPT=%~dp0..\versions\$versionDir\bin\cdx`; `test_windows_installer_launcher_uses_version_directory` covers the generated script template.
- request-AC3 -> This task. Proof: `provider_runtime` now distinguishes `authenticated`, `logged_out`, and `degraded`; CLI tests cover doctor degraded diagnostics, Claude auth timeout preservation, and launch timeout messaging.
- request-AC4 -> This task. Proof: `session_service` validates profile collections and entries before mutation; `test_force_import_rejects_malformed_profile_entries_before_touching_existing_session` confirms credentials remain intact.
- request-AC5 -> This task. Proof: step reports were appended during implementation; final validation ran `npm test`, `npm run release:validate`, `npm run lint`, `logics-manager lint --require-status`, and `logics-manager audit`.

# Validation
- Run `python3 -m logics_manager lint --require-status`.
- Run scaffold command tests.
- Implemented all four follow-up slices. Validation passed: npm test passed 474 tests; npm run release:validate passed; npm run lint passed; targeted release/auth/import tests passed during implementation.
- Finish workflow executed on 2026-07-18.
- Linked backlog/request close verification passed.

# Report
- Implementation complete.
- Step 1-2 implemented: package publication workflows now validate checksums from tagged GitHub Release assets, and install.ps1 now generates a cdx.cmd path with an explicit versionDir. Validation: python3 -m unittest discover -s test -p 'test_release_checksums_py.py' passed.
- Step 3 implemented: provider auth probes now expose authenticated/logged_out/degraded outcomes; codex doctor reports degraded timeout diagnostics; Claude status refresh does not persist logged_out on timeout; launch/run surface an explicit degraded timeout error. Validation: targeted runtime and CLI auth tests passed.
- Step 4 implemented: import bundle profile prevalidation now rejects malformed profile collections and non-object profile entries with CdxError before touching existing session profiles. Validation: targeted session-service force-import tests passed.
- Finished on 2026-07-18.
- Linked backlog item(s): `item_028_use_tagged_release_checksum_assets_in_package_publication_workflows`, `item_029_fix_standalone_windows_installer_launcher_generation`, `item_030_preserve_degraded_auth_semantics_on_provider_probe_timeout`, `item_031_reject_malformed_import_bundle_profile_entries_with_controlled_errors`
- Related request(s): `req_011_address_july_2026_post_remediation_review_follow_up_findings`

# AI Context
- Summary: Orchestrate post-remediation hardening follow-up
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_011_address_july_2026_post_remediation_review_follow_up_findings`
- Product brief(s): `prod_004_post_remediation_hardening_follow_up_2026_07`
- Architecture decision(s): (none yet)
