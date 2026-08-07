## task_036_orchestrate_the_command_module_split - Orchestrate the command module split
> From version: 0.14.0
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Re-measure before starting: handler counts, per-domain line totals, and the helper-to-domain attribution. The plan rests on those numbers and they will have moved since they were taken.
- [ ] 2. Wave 1 - pilot: create the command package, extract the runs domain, put the facade in place, then extract the maintenance domain. Run the full suite after each. Stop here and evaluate.
- [ ] 3. Decision point: if a domain's helpers did not come away as cleanly as measured, or the facade could not keep an import working, re-plan rather than continue. This is the checkpoint the request exists to honor.
- [ ] 4. Wave 2 - remaining domains, one commit each, easiest first, relocating the two cross-group helpers to the shared layer when the first domain that needs them is extracted.
- [ ] 5. Confirm the end state: `cli_commands` defines no handler, every prior import still resolves, `_COMMAND_HANDLERS` is unchanged.
- [ ] 6. Wave 3 - mirror the split in the test file, verifying the collected test count is identical before and after.
- [ ] 7. Run the full suite and `npm run lint`, then `logics-manager lint --require-status` and `logics-manager audit --group-by-doc` before closeout.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_054_pilot_the_split_with_the_runs_and_maintenance_domains`
- `item_055_extract_the_remaining_seven_command_domains`
- `item_056_mirror_the_split_in_the_command_test_file`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1, request-AC2, request-AC4, request-AC5, request-AC6, request-AC8 -> `item_054_pilot_the_split_with_the_runs_and_maintenance_domains`. Proof deferred to slice closeout.
- request-AC1, request-AC2, request-AC3, request-AC4, request-AC5, request-AC8 -> `item_055_extract_the_remaining_seven_command_domains`. Proof deferred to slice closeout.
- request-AC7, request-AC4 -> `item_056_mirror_the_split_in_the_command_test_file`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# AI Context
- Summary: Orchestrate the command module split
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_025_split_cli_commands_into_per_domain_command_modules_behind_a_facade`
- Product brief(s): `prod_015_navigable_command_modules`
- Architecture decision(s): (none yet)
