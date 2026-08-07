## req_024_give_cdx_one_source_of_truth_for_the_values_it_accepts_and_the_provider_flags_it_emits - Give cdx one source of truth for the values it accepts and the provider flags it emits
> From version: 0.13.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Complexity: High
> Theme: Contract integrity
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# Needs
- cdx maintains several hand-written copies of what it accepts, and several hand-written claims about what the provider CLIs accept. Every copy is free to drift from the others, and from reality, with nothing failing when it does.
- The reasoning-effort enum is defined four times and the permission enum twice, across three modules. `cdx set` validates against one pair of copies while `cdx run` validates against another, so the same setting has two definitions in one CLI.
- This has already reached users: `cdx run --permission workspace-write` is accepted and normalized to `default`, while `cdx set <name> --permission workspace-write` fails with `Unsupported permission: workspace-write`. A value copied from one command to the other is rejected.
- `cdx schema --json` was introduced as the discovery surface for programmatic callers, with a drift test — but that test covers only the `cli_args` and `provider_runtime` copies. The three copies in `session_service` are outside it, so the schema presents itself as describing cdx while in fact describing only `cdx run`.
- Nothing verifies that a provider flag cdx is about to emit actually exists in that provider's CLI. GitHub issue #8 was precisely this: `--experimental-yolo` was mapped for ollama, a flag that CLI never had, and it survived undetected until someone exercised `permission=full` on an ollama session.

# Context
- `REASONING_EFFORT_VALUES` (`src/provider_runtime.py:24`), `RUN_EFFORT_VALUES` (`src/cli_args.py:53`), `LAUNCH_POWER_VALUES` (`src/session_service.py:84`), and `LAUNCH_REASONING_EFFORT_VALUES` (`src/session_service.py:85`) all hold the same five values. The last two are byte-identical copies sitting one line apart in the same file.
- `RUN_PERMISSION_CANONICAL_VALUES` (`src/cli_args.py:45`) and `LAUNCH_PERMISSION_VALUES` (`src/session_service.py:86`) hold the same four canonical values, but only `cli_args` also defines the aliases `workspace-write`, `read-only`, and `danger-full-access` and normalizes them.
- `src/session_service.py:131-141` validates launch settings against its own three copies. `cdx run` never reaches that code, and `cdx set` never reaches `cli_args`.
- `cdx schema --json` publishes `RUN_PERMISSION_ALIASES` without stating that the aliases apply to `cdx run` only, so a caller reading the schema and then calling `cdx set` with an advertised alias gets a rejection.
- `LAUNCH_PERMISSION_ARGS` and `HEADLESS_CODEX_PERMISSION_ARGS` (`src/provider_runtime.py:37` and `:51`) map each permission to concrete provider CLI flags. These were verified by hand against the installed CLIs on 2026-08-07 and are currently correct — claude accepts all four mapped modes (`default` being an undocumented but accepted alias), and antigravity accepts `--sandbox` and `--dangerously-skip-permissions`. Correct today is not the point: `--experimental-yolo` was also assumed correct for months.
- `collect_health_report` (`src/health.py:39`) checks the cdx home layout, session profiles and state files, and provider CLI versions. `_provider_capability_hints` (`src/health.py:146`) returns hardcoded prose hints about provider capabilities rather than anything probed. No check exercises a flag cdx will actually pass.

# Acceptance criteria
- AC1: Each accepted-value set is defined once. The reasoning-effort values and the permission values each have a single definition that every validator, normalizer, and the published schema derive from.
- AC2: `cdx set` and `cdx run` accept the same values for `--permission`, `--power`, and `--reasoning-effort`. A value accepted by one is accepted by the other, and the permission aliases work in both.
- AC3: The published `cdx schema --json` describes the whole CLI rather than the run command alone, and the drift test covers every validator that consumes the shared definitions, not a subset of them.
- AC4: A test fails if a second copy of one of these value sets is reintroduced, so the deduplication cannot silently regress.
- AC5: An opt-in health check verifies that the provider CLI flags cdx maps for each permission are actually accepted by that provider's installed CLI, and reports per provider and permission which mappings could not be confirmed.
- AC6: The check is opt-in rather than part of the default `cdx doctor` run, since it costs a provider CLI invocation per provider, and its absence is never reported as a passing result.
- AC7: Existing behavior is preserved for every value that works today: no currently-accepted value becomes rejected, and the normalization of the permission aliases to their canonical forms is unchanged.
- AC8: The README states that the accepted values come from one place, documents that the permission aliases work in both `set` and `run`, and describes the opt-in provider flag check.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_014_one_definition_of_what_cdx_accepts_and_emits`
- Architecture decision(s): (none yet)

# References
- src/cli_args.py
- src/session_service.py
- src/provider_runtime.py
- src/health.py
- src/cli_commands.py
- README.md
- test/test_cli_py.py
- test/test_session_service_py.py
- test/test_health_py.py

# AI Context
- Summary: Give cdx one source of truth for the values it accepts and the provider flags it emits
- Keywords: request-chain-scaffold, give cdx one source of truth for the values it accepts and the provider flags it emits, development-ready
- Use when: You need to implement or review the scaffolded workflow for Give cdx one source of truth for the values it accepts and the provider flags it emits.
- Skip when: The change is unrelated to this scaffolded request chain.

# Backlog
- `item_051_collapse_the_duplicated_accepted_value_enums_into_single_definitions`
- `item_052_accept_the_permission_aliases_in_cdx_set_as_well_as_cdx_run`
- `item_053_add_an_opt_in_check_that_mapped_provider_flags_exist_in_the_provider_cli`
