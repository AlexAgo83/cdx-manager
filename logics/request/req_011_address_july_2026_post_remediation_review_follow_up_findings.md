## req_011_address_july_2026_post_remediation_review_follow_up_findings - Address July 2026 post-remediation review follow-up findings
> From version: 0.10.0
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Operator workflow
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# Needs
- A post-remediation code review found four remaining issues after the July 2026 review corpus was closed: release publication still reads checksum metadata from main, the standalone Windows installer generates a broken launcher, auth probe timeouts are treated as logged-out states, and malformed profile entries in import bundles can raise raw exceptions.
- The follow-up work must close these gaps without reopening the already-completed remediation request, and it must keep the full CLI, release-validation, and Logics validation suites green.

# Context
- Release installers were moved to tagged GitHub Release checksum assets, but package publication workflows still download `checksums/release-archives.json` from the mutable main branch before publishing npm and PyPI artifacts.
- The Windows standalone installer writes `set SCRIPT=%~dp0..\versions\${($tag.TrimStart("v"))}\bin\cdx`; PowerShell does not interpolate that expression in a here-string, so the generated launcher points to `versions\bin\cdx` instead of the installed version directory.
- `_probe_provider_auth` catches `subprocess.TimeoutExpired` and returns False. Callers interpret False as logged out or unauthenticated, which can persist `logged_out` for Claude sessions or block launch/run after a transient hung provider CLI.
- `_validate_import_profile_files` assumes every profile entry is a dictionary before validation. A malformed bundle such as `profiles: {"main": [null]}` raises `AttributeError` instead of a clean `CdxError`, although it happens before disk mutation.

# Acceptance criteria
- AC1: npm and PyPI publish workflows validate release checksums against the tagged GitHub Release asset for the release tag, not against a main-branch checksum file.
- AC2: The standalone Windows installer generates a valid `cdx.cmd` launcher path containing the installed version directory, and a regression test covers the generated script content.
- AC3: Provider auth probe timeouts surface as unknown/degraded probe results, not logged-out results; launch/run/status/doctor callers handle that state explicitly without persisting a false logout.
- AC4: Import bundle profile validation rejects non-object profile entries with `CdxError` before any filesystem mutation, and tests cover the malformed-entry case.
- AC5: Documentation and Logics context describe the remaining release/auth/import contracts accurately, and `npm test`, `npm run release:validate`, `npm run lint`, `logics-manager lint --require-status`, and `logics-manager audit` pass.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_004_post_remediation_hardening_follow_up_2026_07`
- Architecture decision(s): (none yet)

# References
- .github/workflows/publish-npm.yml
- .github/workflows/publish-pypi.yml
- install.ps1
- src/provider_runtime.py
- src/cli_commands.py
- src/session_service.py
- test/test_release_checksums_py.py
- test/test_runtime_py.py
- test/test_session_service_py.py

# AI Context
- Summary: Address July 2026 post-remediation review follow-up findings
- Keywords: request-chain-scaffold, address july 2026 post-remediation review follow-up findings, development-ready
- Use when: You need to implement or review the scaffolded workflow for Address July 2026 post-remediation review follow-up findings.
- Skip when: The change is unrelated to this scaffolded request chain.

# Backlog
- `item_028_use_tagged_release_checksum_assets_in_package_publication_workflows`
- `item_029_fix_standalone_windows_installer_launcher_generation`
- `item_030_preserve_degraded_auth_semantics_on_provider_probe_timeout`
- `item_031_reject_malformed_import_bundle_profile_entries_with_controlled_errors`
