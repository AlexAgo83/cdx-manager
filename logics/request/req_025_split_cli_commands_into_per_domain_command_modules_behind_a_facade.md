## req_025_split_cli_commands_into_per_domain_command_modules_behind_a_facade - Split cli_commands into per-domain command modules behind a facade
> From version: 0.14.0
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Maintainability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-07

# Needs
- `src/cli_commands.py` is 3313 lines and 112 top-level functions, a quarter of the source tree in one file. Finding the handler for a command means scrolling past eight unrelated domains.
- The file is not tangled, it is stacked: its 41 handlers fall into nine domain groups with no remainder, and only 2 of its 71 private helpers are used by more than one group. It is already nine modules sharing a filename.
- The cost of the split is therefore unusually low, which is the whole reason to do it. A split that requires untangling shared state usually is not worth its price; this one requires relocating two helpers.
- This request buys navigation speed, not correctness. It fixes no bug and unblocks no feature, and should be judged on that basis.

# Context
- Measured on the current file: 41 `handle_*` functions totalling 1728 lines, and 71 private helpers totalling 1443 lines.
- Grouping the handlers by domain leaves nothing ungrouped: runs (7 handlers, ~353 lines), maintenance (5, ~326), context and memory (2, ~229), status (7, ~226), auth (4, ~192), launch (5, ~176), session lifecycle (7, ~137), backup (2, ~74), launch settings (3, ~15).
- Of the 71 private helpers, 41 are used by exactly one handler group and move with it. Exactly two are used by more than one: `_resolve_confirmation` (auth, lifecycle, maintenance) and `_bootstrap_claude_setup_token` (auth, lifecycle). The remainder are helpers of helpers rather than cross-group dependencies.
- No helper in the file is dead: every one is referenced from somewhere in `src/` or `test/`. There is no cleanup to fold into this work.
- `src/cli.py` already documents a re-export facade pattern with an `__all__` block explaining that names are imported purely to be re-exported, so keeping `cli_commands` as a facade follows an existing convention rather than inventing one.
- `req_026` decomposes the session service factory. It is deliberately sequenced after this request's pilot, so two structural changes are never in flight over the same test suite.
- `test/test_cli_py.py` is 7116 lines, larger than the module it tests. Its structure mirrors `cli_commands`, so its split is determined by this one and has to follow rather than lead.

# Acceptance criteria
- AC1: Each handler domain lives in its own module, with the private helpers used by only that domain moved alongside it.
- AC2: `cli_commands` remains the import location for every handler it exposes today, so `src/cli.py`, the tests, and any external caller import exactly what they imported before, unchanged.
- AC3: The two genuinely cross-group helpers are relocated to the shared helper layer rather than duplicated or left behind in a module that no longer owns them.
- AC4: No behavior changes: the split is a move. No handler is renamed, no signature changes, and no logic is rewritten in the same commit as a move.
- AC5: The work lands as one commit per extracted domain, each with the full suite passing, so a regression is attributable to a single domain rather than to a 3000-line diff.
- AC6: The extraction of the first two domains is treated as a pilot: if the pattern does not hold cleanly there, the request stops and is re-planned rather than continuing through the remaining seven.
- AC7: `test/test_cli_py.py` is split to mirror the resulting module structure, after the source split has settled.
- AC8: No new abstraction is introduced: no command registry, no base class, no dispatch indirection. The existing `_COMMAND_HANDLERS` dict stays as it is.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_015_navigable_command_modules`
- Architecture decision(s): (none yet)

# References
- src/cli_commands.py
- src/cli.py
- src/cli_helpers.py
- test/test_cli_py.py

# AI Context
- Summary: Split cli_commands into per-domain command modules behind a facade
- Keywords: request-chain-scaffold, split cli_commands into per-domain command modules behind a facade, development-ready
- Use when: You need to implement or review the scaffolded workflow for Split cli_commands into per-domain command modules behind a facade.
- Skip when: The change is unrelated to this scaffolded request chain.

# Backlog
- `item_054_pilot_the_split_with_the_runs_and_maintenance_domains`
- `item_055_extract_the_remaining_seven_command_domains`
- `item_056_mirror_the_split_in_the_command_test_file`
