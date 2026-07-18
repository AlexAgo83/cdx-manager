## req_010_address_july_2026_code_review_findings_data_safety_reliability_and_cleanup - Address July 2026 code review findings: data-safety, reliability, and cleanup
> From version: 0.10.0
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Operator workflow
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# Needs
- A full code review (2026-07-18, three parallel reviewers over src/, CLI layer, and packaging) found one data-loss risk, three auth-reliability defects, five robustness/UX bugs, one Windows npm-entrypoint gap, one supply-chain weakness, and a set of duplication/dead-code/docs issues.
- All findings must be fixed without regressing current behavior: 454 tests green, atomic-write and quarantine-before-delete discipline preserved, AES-256-GCM bundle handling unchanged.

# Context
- Highest severity: `cdx import --force` deletes each existing session profile (auth.json, claude-home credentials) before re-import with no per-session rollback; a bundle exported without --include-auth restores nothing, permanently logging out every overwritten session (src/session_service.py:1368-1427).
- Auth reliability: provider auth probes (`codex login status` / `claude auth status`) run with no subprocess timeout on every launch/run/doctor (src/provider_runtime.py:913-917) while the equivalent probe in claude_usage.py:98 uses 15s; the codex auth lock is non-blocking but the body executes anyway when contended, allowing the concurrent auth.json refresh it exists to prevent (src/provider_runtime.py:959, src/codex_usage.py:39-44); a stored `reasoning_effort` launch key permanently shadows `--power` because set does not clear it and unset does not allow it (src/session_service.py:899-926).
- Robustness/UX: one truncated JSONL line makes `cdx history` fail forever (src/session_store.py:296-298) while run_usage._parse_json_records skips bad lines; `cdx status` crashes entirely if a session is removed concurrently (src/session_service.py:1217-1219); bare `cdx clean profiles` and the `--old-logs=N` equals-form are misrouted as a session name (src/cli_commands.py:1738); `cdx disk --candidates` validates argument combinations only after the full du scan (src/cli_commands.py:551 vs 562); `cdx view --json` returns ok:true and exit 0 when logics-manager is missing (src/cli_view.py:91-93).
- Entrypoint: the npm launcher bin/cdx calls main() directly, duplicating cli_entry error handling and skipping _enable_windows_ansi()/_configure_windows_encoding() (src/cli.py:605-607), so npm-installed Windows users get raw ANSI escapes and potential UnicodeEncodeError.
- Supply chain: install.sh/install.ps1 verify release archives against checksums fetched from the same repository main branch as the artifact (shared trust root), and the CDX_ALLOW_UNVERIFIED=1 escape hatch skips verification with only a quiet notice.
- Cleanup: three drifting copies of the update-warning payload builder (cli.py:429, cli_helpers.py:68, cli_view.py:16); two independent _format_bytes implementations (cli_commands.py:174, cli_helpers.py:106); two ~90%-identical progress factories (cli_helpers.py:160-210); duplicated limit-parsing regexes (status_source.py:23-26 vs 521-533); dead code (_update_notice_warning, speculative asyncio branch in claude_refresh.py:51-65, shutil_which stdlib re-wrap); hygiene drift (.gitignore lists tracked logics.yaml/LOGICS.md, README stale Python 3.9 note, cdx run --help omits --kind, cdx stats errors print the history command usage).

# Acceptance criteria
- AC1: `cdx import --force` never destroys credentials it cannot restore: importing a bundle without auth payloads over existing sessions is refused with an explicit message unless an explicit override flag is passed, and each session import validates all bundle content (base64, safe paths) before touching disk, renames the old profile aside, restores it on failure, and purges the backup on success.
- AC2: Provider auth probes run with a bounded timeout (15s, aligned with claude_usage) and a timeout yields an unknown/degraded status instead of hanging launch/run/doctor.
- AC3: The codex auth lock waits with a bounded retry when contended instead of executing unlocked; if the lock cannot be acquired within the bound, the operation fails or degrades explicitly rather than racing the auth refresh.
- AC4: `cdx set <name> --power X` clears any stored reasoning_effort so the new power takes effect, and `cdx unset` accepts reasoning_effort; a session can no longer report one power and launch with another.
- AC5: `cdx history` tolerates corrupt/truncated JSONL lines by skipping them (optionally reporting a skipped count) instead of raising, matching run_usage parsing behavior.
- AC6: `cdx status` skips or marks a session removed concurrently during the scan instead of crashing the whole table.
- AC7: `cdx clean profiles` (bare) prints the profiles-clean usage, and both `--old-logs N` and `--old-logs=N` forms route to the profiles branch; no clean invocation is misrouted as a session name.
- AC8: `cdx disk` validates argument combinations before starting any directory scan.
- AC9: `cdx view --json` reports ok:false and a non-zero exit code when the viewer cannot run (logics-manager missing), consistent with the non-JSON path.
- AC10: The npm launcher routes through cli_entry() so Windows ANSI/encoding setup and error handling are applied identically for npm and pip installs, removing the duplicated error handling in bin/cdx.
- AC11: Release checksums are verified against a source independent of the main branch (e.g. tagged GitHub Release assets), and enabling CDX_ALLOW_UNVERIFIED prints a prominent multi-line warning.
- AC12: Duplicated helpers are unified (single update-warning builder, single _format_bytes, single progress factory, single set of status_source limit regexes) and dead code is removed (_update_notice_warning, claude_refresh asyncio branch, shutil_which), with all call sites migrated.
- AC13: Docs/config hygiene is fixed: .gitignore no longer lists tracked files, README Python-support note matches 0.10.x reality, `cdx run --help` documents --kind, and `cdx stats` argument errors print the stats usage.
- AC14: Non-regression tests cover the JSONL tolerance, clean-profiles routing, view --json failure contract, and npm entrypoint wiring; the full suite stays green.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_003_code_review_remediation_wave_2026_07`
- Architecture decision(s): (none yet)

# References
- src/session_service.py
- src/provider_runtime.py
- src/session_store.py
- src/cli_commands.py
- src/cli_view.py
- src/cli_helpers.py
- src/cli.py
- bin/cdx
- install.sh
- install.ps1

# AI Context
- Summary: Address July 2026 code review findings: data-safety, reliability, and cleanup
- Keywords: request-chain-scaffold, address july 2026 code review findings: data-safety, reliability, and cleanup, development-ready
- Use when: You need to implement or review the scaffolded workflow for Address July 2026 code review findings: data-safety, reliability, and cleanup.
- Skip when: The change is unrelated to this scaffolded request chain.

# Backlog
- `item_022_safe_bundle_import_pre_validation_credential_guard_per_session_rollback`
- `item_023_provider_auth_reliability_probe_timeout_bounded_auth_lock_power_effort_precedence`
- `item_024_cli_robustness_tolerant_history_parsing_concurrent_removal_safe_status_clean_disk_view_fixes`
- `item_025_unify_npm_entrypoint_through_cli_entry`
- `item_026_release_verification_trust_root_and_unverified_install_warning`
- `item_027_deduplication_dead_code_removal_and_docs_hygiene`
