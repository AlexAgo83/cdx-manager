## req_029_settle_what_0_15_0_left_behind_before_cutting_0_15_1 - Settle what 0.15.0 left behind before cutting 0.15.1
> From version: 0.15.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Release hygiene and CLI surface
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# Needs
- 0.15.0 shipped and three things did not settle with it. One is a traceability record that now claims less than the truth, one is a concurrency failure on a supported platform under exactly the load cdx is built for, and one is a class of defect this codebase produced during that very release and can produce again.
- `req_028`'s closeout records AC11 as `unverified` and says background delegation is 'disabled rather than shipped broken'. That was accurate when written. It was then made to work and verified end to end - launch, closeout with usage read from the provider's session transcript, and the parked session stopped. The record is now the same kind of untruth this project spent a release fighting, only in the other direction: a document asserting less verification than actually happened is as useless as one asserting more.
- `test_concurrent_starts_do_not_lose_records` fails on a real Windows machine with `OSError(36, 'Resource deadlock avoided')` under twenty concurrent writers. It passes in CI and reproduces identically on the `v0.14.0` tag, so it predates this work - which is why it was set aside. That framing understates it: the scenario is a fleet of parallel runs each writing the run registry, which is the load cdx exists to carry, on one of its two supported platforms.
- Adding `--failover` during 0.15.0 required five coordinated edits: usage string, parser table, schema exclusivity declaration, conflict check, and the returned dict. One was missed - the returned dict - and the flag parsed, validated and documented while doing nothing at all. No error, no failing test until an integration test happened to catch it. The same shape recurred for `--budget`, `--fallback-model` and `--extra-args`, each touching five to eight files.
- The fix for `rate_limit_reached` is already on main and unreleased. It corrects a false negative in `--failover`: an account whose credits are depleted while both percentage windows still read healthy was reported as not exhausted, so a run that could not possibly succeed was never migrated. Shipping it is the point of 0.15.1, and it should not ship alone.

# Context
- `_registry_lock` in `src/run_registry.py:18` uses `msvcrt.locking(fileno, LK_LOCK, 1)` on Windows and `fcntl.flock` elsewhere. `LK_LOCK` retries ten times at one-second intervals and then raises `EDEADLOCK`; there is no retry above it, so contention beyond that budget surfaces to the caller as an `OSError` rather than as a wait. The POSIX branch blocks indefinitely instead, so the two platforms do not behave alike under contention.
- The option layer is already table-driven - `_parse_flag_args` in `src/cli_args.py:118` consumes a schema dict - but the table is not the only source. A single option is currently declared in the parser table, in one or two usage strings, in the returned dict, in the unset key tuple, in `_normalize_launch_settings`, in the `unset_launch_settings` allow-set, in the display list in `src/cli_helpers.py`, in `_format_launch_configs` in `src/commands/status.py`, and in the provider argument mapping.
- Measured touch points for existing options: `budget` appears in 7 files, `fallback_model` in 5, `extra_args` in 8, `rtk` in 9, `priority` in 11. The count is the symptom; which of those are genuinely independent decisions and which are mechanical restatements is the question a design has to answer, and nobody has measured that yet.
- This project has an established precedent for that: `req_027` measured coupling by transitive closure before splitting `session_service`, and the measurement is what said to stop after two modules rather than six. A measurement pass on the option layer is the equivalent, and it exists because the same author's intuition about `provider_runtime` was half wrong once measured.
- `item_051` already collapsed duplicated accepted-value enums into single definitions, and `src/session_service.py` records why: three separate literals validated independently are how `cdx set` and `cdx run` came to disagree about the same setting. The CLI option layer never received that treatment.
- `cdx schema --json` derives its enums and mutually-exclusive groups from the parser's own definitions, and callers depend on it. Any consolidation has to keep that derivation intact rather than replacing it with a second description.
- The repository has one runtime dependency, `cryptography`, and five installation channels. Adopting Typer or Click would add a runtime dependency to all of them, which is a cost this project has consistently declined.

# Acceptance criteria
- AC1: `req_028`'s AC11 record states what was actually verified about background delegation - that it works, how it was observed, and that it remains opt-in for exposure reasons rather than for correctness ones - and the request's own criterion is marked accordingly.
- AC2: The claim in `CHANGELOGS_0_15_0.md` that background delegation is off because it 'has been exercised far less' remains accurate, or is corrected if the closeout revision contradicts it.
- AC3: Twenty concurrent writers to the run registry all succeed on Windows, with no `OSError` reaching the caller, and `test_concurrent_starts_do_not_lose_records` passes on a real Windows machine rather than only in CI.
- AC4: Lock acquisition behaves equivalently on both platforms under contention - a waiter waits rather than failing - and the difference between `LK_LOCK`'s bounded retry and `flock`'s indefinite block is either removed or documented as deliberate.
- AC5: A caller that cannot acquire the lock within a bounded time receives a specific, actionable error rather than a raw `OSError`, so an exhausted wait is distinguishable from a bug.
- AC6: The option layer's touch points are measured and published - which declarations are independent decisions and which are mechanical restatements of the same fact - before any consolidation design is chosen.
- AC7: Adding one option to `cdx set` requires one declaration, and a declaration that is incomplete fails loudly at import or test time rather than producing a flag that parses and does nothing.
- AC8: `cdx schema --json` still derives its enums, mutually-exclusive groups and error codes from the same definitions the parser uses, with no second description of the same facts.
- AC9: No runtime dependency is added.
- AC10: The regression that motivated this - a flag present in the parser table but absent from the returned dict - is impossible to express, and a test demonstrates that the failure mode is now caught.
- AC11: 0.15.1 ships with the `rate_limit_reached` fix, the registry lock fix, and a changelog that says which of 0.15.0's stated gaps have closed.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_019_settle_0_15_0_s_remainder`
- Architecture decision(s): (none yet)

# References
- src/run_registry.py
- src/cli_args.py
- src/session_service.py
- src/cli_helpers.py
- src/commands/status.py
- src/provider_runtime.py
- src/run_failover.py
- src/status_source.py
- logics/tasks/task_039_orchestrate_executable_quota_routing_across_accounts_and_providers.md
- test/test_run_registry_py.py
- test/test_run_failover_py.py
- changelogs/CHANGELOGS_0_15_0.md

# AI Context
- Summary: Settle what 0.15.0 left behind before cutting 0.15.1
- Keywords: request-chain-scaffold, settle what 0.15.0 left behind before cutting 0.15.1, development-ready
- Use when: You need to implement or review the scaffolded workflow for Settle what 0.15.0 left behind before cutting 0.15.1.
- Skip when: The change is unrelated to this scaffolded request chain.

# Backlog
- `item_068_correct_the_req_028_record_to_state_what_background_delegation_was_actually_verified_to_do`
- `item_069_let_concurrent_writers_wait_for_the_run_registry_lock_on_windows_instead_of_failing`
- `item_070_measure_what_a_single_option_actually_costs_before_designing_anything`
- `item_071_make_an_incomplete_option_declaration_impossible`
- `item_072_cut_0_15_1_once_the_rest_has_settled`
