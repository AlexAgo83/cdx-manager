## req_022_unify_the_two_divergent_session_selection_rankings_into_one_contract - Unify the two divergent session selection rankings into one contract
> From version: 0.13.0
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: High
> Theme: Session selection
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-07

# Needs
- cdx answers the question 'which session should this work go to' with two independent ranking algorithms that do not agree, and a user cannot tell from the outside which one a given command consulted.
- `_select_headless_session` (`src/cli_commands.py:1571`) backs `cdx select` and `cdx run --provider`. `_recommend_priority_sessions` (`src/status_view.py:202`) backs `cdx next`, the `cdx status` recommendation line, and — through `resolve_notify_event` (`src/notify.py:102`) — `cdx notify --next-ready` and `cdx ready`, which `src/cli.py:547` rewrites into the notify path.
- The divergence is not cosmetic. The per-session `--priority` setting is honored only by the headless ranking; `cdx next` ignores it entirely. Conversely credits and reset scheduling are weighed only by the recommendation ranking, which the headless path never consults.
- The naming actively misleads. `cdx next` prints a `Priority:` line produced by `_priority_instruction` (`src/status_view.py:249`), which has nothing to do with the `--priority` value a user set with `cdx set <name> --priority 90`. A user who tunes `--priority` and then runs `cdx next` to see the effect observes no change and has no way to learn why.
- `req_023` covers the reporting half — the hardcoded `selection_policy` and `reason` strings that already misdescribe today's ranking. It is deliberately separable and smaller; this request changes the rule, that one changes cdx's account of it.
- Two rankings also means two places to fix any future selection rule, and no single definition to publish to programmatic callers now that `cdx schema --json` exists as the discovery surface.

# Context
- `_select_headless_session` filters to one provider and to enabled sessions, optionally drops sessions failing `_row_blocks_ready` when `require_ready` is set, then sorts on the tuple `(-cooldown, -available_pct, -priority, reasoning_rank, name)` where `cooldown` is simply `available_pct > 0`.
- `_recommend_priority_sessions` does not filter by provider at all. It buckets rows into four tiers — usable now, blocked but with a known future reset, reset known, everything else — and ranks within a tier on credits, reset timestamp, available percentage, and name. It never reads the session's `--priority` setting, and status rows do not even carry that field.
- `recommend_priority_rows` (`src/status_view.py:189`) additionally drops rows whose auth status formats as `logged out`. The headless path applies its auth filter only when `require_ready` is true, so the two disagree on whether a logged-out session is a candidate.
- In the headless sort tuple every term is negated for descending order except `reasoning_rank`, which stays positive and therefore sorts ascending. Two otherwise-equal sessions resolve in favour of the *lower* configured reasoning effort. That may be a deliberate cost preference, but it is undocumented and is the kind of rule that should be stated rather than inferred from a sign.
- `_session_reasoning_effort` (`src/cli_commands.py:1535`) falls back to `low` when a session configures no effort, so `--min-reasoning-effort medium` excludes every unconfigured session regardless of what its provider actually defaults to.
- `cdx run --provider` calls the selector with `force_refresh=False` hardcoded (`src/cli_commands.py:1248`) and exposes no way to change it, so auto-selection can decide on status data that was never fetched. A session with no recorded `available_pct` sorts as `-1.0`, behind a session sitting at one percent of its quota.

# Acceptance criteria
- AC1: One ranking function decides session selection for every command that selects a session, parameterized by what each caller actually needs (provider filter on or off, readiness required or not) rather than duplicated per caller.
- AC2: The unified ranking preserves the capabilities currently unique to each side: the provider filter and the `--priority` setting from the headless path, and the credits, reset-scheduling, and tiering behavior from the recommendation path.
- AC3: A session's `--priority` setting measurably affects `cdx next`, `cdx status`'s recommendation, and `cdx ready`, not only `cdx select` and `cdx run --provider`. Raising one session's priority moves it ahead of an otherwise-equal session in every one of those commands.
- AC4: `cdx select`, `cdx run --provider`, `cdx next`, and `cdx ready` agree on which session is best when given the same sessions, the same status rows, and equivalent constraints. A test asserts that agreement directly rather than testing each command in isolation.
- AC5: The tie-break on reasoning effort is explicit and documented, whichever direction it settles on, instead of being implied by an un-negated term in a sort tuple.
- AC6: The naming distinguishes the user-set `--priority` value from the recommendation ranking, so a `Priority:` line in cdx output and the `--priority` setting no longer refer to different things.
- AC7: Selection behavior is unchanged for cases where the two rankings already agreed; the request unifies the rule, it does not silently retune which session gets picked in the common case.
- AC8: The README documents the single selection rule once, and states how `--priority`, availability, resets, credits, and reasoning effort combine.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_012_one_session_selection_rule_across_every_command`
- Architecture decision(s): (none yet)

# References
- src/cli_commands.py
- src/status_view.py
- src/notify.py
- src/cli.py
- src/session_service.py
- README.md
- test/test_cli_py.py
- test/test_status_view_py.py
- test/test_notify_py.py

# AI Context
- Summary: Unify the two divergent session selection rankings into one contract
- Keywords: request-chain-scaffold, unify the two divergent session selection rankings into one contract, development-ready
- Use when: You need to implement or review the scaffolded workflow for Unify the two divergent session selection rankings into one contract.
- Skip when: The change is unrelated to this scaffolded request chain.

# Backlog
- `item_047_extract_one_parameterized_session_ranking_used_by_every_selector`
- `item_048_make_the_priority_setting_count_in_next_status_and_ready`
