## req_028_turn_quota_awareness_from_advice_into_execution_across_accounts_and_providers - Turn quota awareness from advice into execution across accounts and providers
> From version: 0.14.0
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: High
> Theme: Quota-aware execution
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-08

# Needs
- cdx knows, across every registered account, which one has quota left. That knowledge is applied exactly once - before the work starts - and never again at the moment it matters, which is when a run hits the wall mid-task. `cdx status` reports, `cdx next` recommends, and then the user is on their own.
- `cdx run` selects a session at launch through `_select_headless_session` and dies with it. There is no rate-limit detection anywhere in the codebase: the only retry in `src/provider_runtime.py` is `_should_retry_without_transcript`, which relaunches without transcript capture after a `script` failure and has nothing to do with quota. A long headless task therefore fails at the first limit even when four other registered accounts are at 100%.
- The provider CLIs have moved. Claude Code 2.1.226 now ships `--max-budget-usd` (hard spend ceiling), `--fallback-model` (automatic model fallback), `--session-id <uuid>`, `--fork-session`, and native background execution via `--bg` plus `claude agents`. codex-cli 0.147.0 ships `resume`, `fork`, `archive`, `cloud`, and `exec-server`. cdx maps none of these except `--effort` and `--model`.
- Mapping provider flags one at a time is a treadmill cdx will lose: both CLIs ship new flags faster than cdx can adopt them, and every unmapped flag is a user who has to stop using cdx to get at it. There is currently no escape hatch of any kind - a user who needs `--add-dir` or `--allowedTools` must abandon the isolation cdx provides.
- cdx hand-rolls detached execution in `_spawn_detached_run` (PID tracking, `start_new_session`, a child argv rebuilt by `_detached_child_argv`) while both providers now ship background execution natively. Continuing to deepen the in-house mechanism spends effort on the one part of the problem the providers will solve themselves, instead of the part only cdx can solve: routing across accounts neither provider can see.
- The differentiator is compositional, not inventive: ranking (`rank_sessions`), run tracking (`RunRegistry`), and cross-provider context transfer (`handoff`, which already builds context from a source session's transcript and installs it into a target) all exist independently and have never been wired into a single loop.

# Context
- Launch settings follow one established pattern across `src/session_service.py` (`_normalize_launch_settings`, and the allowed-key set in `unset_launch_settings`), `src/cli_args.py` (the `--power`/`--permission`/`--fast`/`--rtk`/`--logics`/`--model`/`--priority` tables), `src/cli_helpers.py` (the display label list), `src/commands/status.py` (`_format_launch_configs`) and `src/provider_runtime.py` (argument mapping). `rtk` is the most recent addition and is the reference implementation to mirror.
- `--max-budget-usd` and `--fallback-model` are Claude Code flags with no Codex equivalent. cdx already has precedent for provider-specific launch settings: `_launch_config_args` maps `power` to `-c model_reasoning_effort=` for Codex and to `--effort` for Claude, and `cdx doctor --check-provider-flags` exists specifically to verify that mapped flags are accepted by the installed provider CLI.
- Native resume is recency-based, not identity-based. `get_resume_capability` in `src/provider_runtime.py:555` returns `codex resume --last --cd <cwd>` for Codex and `claude --continue` for Claude. Both mean 'the most recent conversation here', so resume depends on directory and ordering rather than on a session cdx can name. Claude's `--session-id <uuid>` and Codex's `resume <id>` make an identity-based form available for the first time.
- `handoff` reconstructs context by reading a source session's launch transcript (`_latest_handoff_transcript_path`, `_read_handoff_transcript`, `_build_handoff_context` in `src/commands/launch.py`) and installing the result as the workspace context. It works, and it is the only cross-provider context transfer that exists, but scraping a terminal transcript is a weaker foundation than a provider-native session identifier for anything that must be reliable unattended.
- `RunRegistry` (`src/run_registry.py`) records one session and one provider per run through `start()` and closes it with `finish(status=...)`. It has no representation for a run that moved between sessions, so a failover would currently be invisible in `cdx runs` and `cdx run-report`.
- `rank_sessions` and `selection_policy` in `src/session_ranking.py` are already the single ranking shared by `cdx next`, `cdx select`, `cdx status` and `cdx run`, so re-selection mid-run needs no new selection logic - only a caller.
- The ollama provider is explicitly out of scope for this request. The maintainer uses the ollama CLI directly alongside cdx, and the overlap with `codex --oss --local-provider ollama` is a deliberate non-goal rather than a duplication to resolve.

# Acceptance criteria
- AC1: `cdx set <name> --budget <amount>` persists a per-session spend ceiling, `cdx configs` displays it, `cdx unset <name> --budget` clears it, and a non-positive or non-numeric amount is rejected with a specific error rather than being silently stored.
- AC2: `cdx set <name> --fallback-model <model>` persists a per-session fallback model, validated with the same character and length rules as `--model`, and both settings survive a launch/relaunch cycle exactly as `power` and `permission` do.
- AC3: For a Claude session carrying either setting, a **headless** run includes `--max-budget-usd` and `--fallback-model` respectively, while interactive launches, resume, and every Codex launch include neither; both flags are `--print`-only in Claude Code 2.1.226, so this is a provider constraint rather than a cdx choice, and `cdx configs` reports where each setting applies rather than failing a launch.
- AC4: cdx records a provider-native session identifier, and its provenance, for each session that supports one - imposed for Claude through `--session-id`, observed for Codex by reading the rollout's `session_id` after a run - and `cdx resume <name>` uses that identifier instead of the recency heuristics `codex resume --last` and `claude --continue`, so resuming is unaffected by the working directory or by other sessions having run more recently.
- AC5: `cdx can-resume <name> --json` reports which resume strategy will actually be used (identity-based or recency-based) and why, so a caller can tell a reliable resume from a best-effort one before relying on it.
- AC6: `cdx run --failover` detects that a run has terminated because of a provider rate limit, distinguishes that cause from every other failure, corroborates it against the account's own refreshed status before acting, re-ranks the remaining sessions, transfers the working context, and continues the task on the next eligible session without user intervention; every ambiguous case is biased towards not failing over, because a false positive migrates a healthy run off a working account.
- AC7: A run that failed over is fully traceable: `cdx run-report <run_id> --json` names every session the run occupied, in order, with the reason for each transition, and `cdx runs` shows the run as one run rather than as several unrelated ones.
- AC8: When no eligible session remains, a failover run terminates with a specific error code that distinguishes 'exhausted every account' from 'the task itself failed', and reports what was attempted.
- AC9: A user can pass provider arguments cdx does not model, per session (`cdx set --extra-args`) and per run, and those arguments reach the provider command line unmodified.
- AC10: Passthrough arguments are documented and reported as unvalidated: they are excluded from the `cdx schema --json` contract and from `cdx doctor --check-provider-flags`, and cdx never claims to have verified them.
- AC11: Where the installed provider CLI offers native background execution, `cdx run --detach` delegates to it rather than to the in-house detached launcher, decided by capability detection against the installed CLI rather than by a version assumption.
- AC12: When the installed CLI offers no native background execution, the existing in-house detached path continues to work exactly as it does today, and which path was taken is visible in the run record.
- AC13: No behaviour of the `ollama` provider changes anywhere in this request.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_018_executable_quota_routing`
- Architecture decision(s): (none yet)

# References
- src/session_service.py
- src/session_ranking.py
- src/session_status.py
- src/provider_runtime.py
- src/cli_args.py
- src/cli_helpers.py
- src/commands/runs.py
- src/commands/launch.py
- src/commands/settings.py
- src/run_registry.py
- src/context_store.py
- README.md
- test/test_commands_runs_py.py
- test/test_commands_settings_py.py
- test/test_commands_launch_py.py
- test/test_runtime_py.py
- test/test_session_service_py.py

# AI Context
- Summary: Turn quota awareness from advice into execution across accounts and providers
- Keywords: request-chain-scaffold, turn quota awareness from advice into execution across accounts and providers, development-ready
- Use when: You need to implement or review the scaffolded workflow for Turn quota awareness from advice into execution across accounts and providers.
- Skip when: The change is unrelated to this scaffolded request chain.

# Backlog
- `item_063_add_budget_and_fallback_model_as_pinnable_launch_settings`
- `item_064_anchor_resume_and_handoff_on_a_provider_native_session_identity`
- `item_065_continue_a_headless_run_on_the_next_eligible_account_after_a_rate_limit`
- `item_066_pass_unvalidated_provider_arguments_through_instead_of_mapping_every_flag`
- `item_067_delegate_background_execution_to_the_provider_where_the_installed_cli_supports_it`
