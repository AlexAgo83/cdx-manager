## task_036_orchestrate_the_command_module_split - Orchestrate the command module split
> From version: 0.14.0
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
- [x] 1. Re-measure before starting: handler counts, per-domain line totals, and the helper-to-domain attribution. The plan rests on those numbers and they will have moved since they were taken. Done: 41 handlers / 71 helpers unchanged, but the shared-helper count is 9 rather than 2 once the transitive closure is used.
- [x] 2. Wave 1 - pilot: create the command package, extract the runs domain, put the facade in place, then extract the maintenance domain. Run the full suite after each. Stop here and evaluate. Done in `3e42788` and `3429fc3`, 560 tests passing after each.
- [x] 3. Decision point: if a domain's helpers did not come away as cleanly as measured, or the facade could not keep an import working, re-plan rather than continue. This is the checkpoint the request exists to honor. Evaluated: both conditions fired in a bounded way - the helper attribution was understated and one patch target could not be covered - but neither invalidates the pattern. See the pilot outcome in `item_054`. Continuing with the transitive closure as the extraction unit.
- [x] 4. Wave 2 - remaining domains, one commit each, easiest first, relocating the two cross-group helpers to the shared layer when the first domain that needs them is extracted. Done: seven domains in seven commits, plus one commit relocating all eight shared helpers together rather than one at a time - see the deviation note in `item_055`.
- [x] 5. Confirm the end state: `cli_commands` defines no handler, every prior import still resolves, `_COMMAND_HANDLERS` is unchanged. Confirmed: 264 lines, zero definitions, 42 handlers importable, dispatch unchanged at 40 entries.
- [x] 6. Wave 3 - mirror the split in the test file, verifying the collected test count is identical before and after. Done in `f766858`: 16 modules, 561 collected before and after, every body verified byte-identical against HEAD.
- [x] 7. Run the full suite and `npm run lint`, then `logics-manager lint --require-status` and `logics-manager audit --group-by-doc` before closeout.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_054_pilot_the_split_with_the_runs_and_maintenance_domains`
- `item_055_extract_the_remaining_seven_command_domains`
- `item_056_mirror_the_split_in_the_command_test_file`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_054`, `item_055`. Proof: nine modules under `src/commands/`, each holding its domain's handlers plus the helpers reached only from them; attribution computed as a transitive closure, not direct calls.
- request-AC2 -> `item_054`, `item_055`. Proof: `cli_commands.py` re-exports all 42 handlers and every helper its callers import; `test_cli_commands_facade_still_exposes_every_name_its_callers_import` asserts it and was verified to fail when a re-export is dropped.
- request-AC3 -> `item_055`. Proof: the cross-domain helpers live once in `cli_helpers` (`387f292`). There were nine, not two: the original count measured direct calls only.
- request-AC4 -> `item_054`, `item_055`, `item_056`. Proof: extractions cut definitions verbatim; the 264 moved test bodies were diffed against HEAD and 0 differ. No handler renamed, no signature changed.
- request-AC5 -> `item_054`, `item_055`. Proof: nine extraction commits (`3e42788`, `3429fc3`, `783fdee`, `23c5818`, `a83eb36`, `f9d5c81`, `a972e1d`, `735476b`, `d403570`), full suite green after each.
- request-AC6 -> `item_054`. Proof: the pilot stopped at two domains and was evaluated before wave 2; both checkpoint conditions fired in a bounded way and the outcome is recorded in `item_054` rather than assumed.
- request-AC7 -> `item_056`. Proof: 16 test modules mirroring the source shape (`f766858`); 561 collected before and after, coverage unchanged at 82%.
- request-AC8 -> `item_054`, `item_055`. Proof: no registry, base class or dispatch indirection added; `_COMMAND_HANDLERS` is unchanged at 40 entries.

# Validation
- `npm run lint` clean; 561 tests pass; `--cov` totals identical before and after the split (82%, same statement and branch counts).
- `logics-manager flow validate` 0 findings; `logics-manager lint --require-status` OK.

# Report
- All three slices delivered. `cli_commands.py` went 3313 -> 264 lines and defines nothing; the nine domains live in `src/commands/`, the eight cross-domain helpers in `cli_helpers`, and the test file mirrors the same shape across 16 modules.
- 561 tests pass, coverage unchanged at 82%, `npm run lint` clean.
- Two gaps the split exposed outside its own scope: the `py_compile` globs in `package.json` and `.github/workflows/ci.yml` matched neither `src/commands/` nor the new test support module, and the accepted-value dedup guard only globbed `src/*.py`. All widened.
- A facade guard test now fails if any future change drops a re-export, which is the failure mode this shape introduces.

# AI Context
- Summary: Orchestrate the command module split
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_025_split_cli_commands_into_per_domain_command_modules_behind_a_facade`
- Product brief(s): `prod_015_navigable_command_modules`
- Architecture decision(s): (none yet)
