## task_021_orchestrate_july_2026_code_review_remediation - Orchestrate July 2026 code review remediation
> From version: 0.10.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Land the safe-bundle-import backlog item first (only data-loss risk), with its refusal-and-rollback tests.
- [x] 2. Land provider auth reliability (probe timeout, bounded lock, power/effort precedence) as one change set.
- [x] 3. Land the CLI robustness fixes with one regression test per fix.
- [x] 4. Unify the npm entrypoint through cli_entry.
- [x] 5. Move release checksum verification to tagged release assets and add the unverified-install warning.
- [x] 6. Finish with the dedup/dead-code/docs chore commit.
- [x] 7. Run the full test suite and release verification scripts after each step; keep 454+ tests green.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_022_safe_bundle_import_pre_validation_credential_guard_per_session_rollback`
- `item_023_provider_auth_reliability_probe_timeout_bounded_auth_lock_power_effort_precedence`
- `item_024_cli_robustness_tolerant_history_parsing_concurrent_removal_safe_status_clean_disk_view_fixes`
- `item_025_unify_npm_entrypoint_through_cli_entry`
- `item_026_release_verification_trust_root_and_unverified_install_warning`
- `item_027_deduplication_dead_code_removal_and_docs_hygiene`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> item_022. Proof: force auth-less import refusal and invalid profile payload rollback tests pass.
- request-AC2 -> item_023. Proof: auth probe timeout regression passes.
- request-AC3 -> item_023. Proof: Codex auth lock timeout regression passes.
- request-AC4 -> item_023. Proof: set power clears stored reasoning effort and unset reasoning effort regressions pass.
- request-AC5 -> item_024. Proof: launch history skips torn JSONL regression passes.
- request-AC6 -> item_024. Proof: status skips concurrently removed session regression passes.
- request-AC7 -> item_024. Proof: clean profiles routing and `--old-logs=N` regressions pass.
- request-AC8 -> item_024. Proof: disk candidates rejects invalid target before scan regression passes.
- request-AC9 -> item_024. Proof: view JSON missing viewer returns `ok:false` and exit 1 regression passes.
- request-AC10 -> item_025. Proof: bin launcher delegates to `cli_entry()` regression passes.
- request-AC11 -> item_026. Proof: installer checksum URL static regression and release checksum validation pass.
- request-AC12 -> item_027. Proof: grep confirms removed duplicate/dead helper symbols have no production references.
- request-AC13 -> item_027. Proof: help/stats/docs hygiene regressions pass.
- request-AC14 -> item_024/item_025. Proof: full `npm test` passed 468 tests.

# Validation
- Run `python3 -m logics_manager lint --require-status`.
- Run scaffold command tests.

# Report
- Implementation complete across six commits for backlog items `item_022` through `item_027`.
- Final validation: `npm test`; `npm run release:validate`; `npm run lint`; `logics-manager lint --require-status`; `logics-manager audit`.

# AI Context
- Summary: Orchestrate July 2026 code review remediation
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_010_address_july_2026_code_review_findings_data_safety_reliability_and_cleanup`
- Product brief(s): `prod_003_code_review_remediation_wave_2026_07`
- Architecture decision(s): (none yet)
