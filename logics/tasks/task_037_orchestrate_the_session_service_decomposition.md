## task_037_orchestrate_the_session_service_decomposition - Orchestrate the session service decomposition
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
- [x] 1. Do not start before `req_025`'s pilot has reported. Honoured: `req_025` was closed before this task started.
- [x] 2. Measure first: for each of the 46 closures, list exactly which factory locals it references. Done: 19 capture nothing directly but only 11 transitively, which is what actually drives `item_057`.
- [x] 3. Wave 1 - lift the closures that capture nothing to module level. Done in `ed1d3de`: 11 lifted, factory 1154 -> 1014 lines.
- [x] 4. Wave 2 - state-dependent closures by concern cluster. Done in five commits ending `a0455f3`: factory 1014 -> 56 lines, zero closures left.
- [x] 5. Confirm the interface. Confirmed after every cluster by diffing the returned dict's keys against the pre-request build: 29 keys, identical, no caller touched.
- [x] 6. Wave 3 - coupling measured and decision recorded in `item_059`: split along `status` and `backup` only, as a separate request; `runtime` and `auth` have zero exclusive helpers and must not become files.
- [x] 7. Run the full suite and `npm run lint`, then `logics-manager lint --require-status` and `logics-manager audit --group-by-doc` before closeout.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_057_lift_the_closures_that_capture_nothing_into_module_level_functions`
- `item_058_give_the_state_dependent_closures_explicit_dependencies`
- `item_059_decide_the_file_split_from_the_seams_the_decomposition_exposed`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_057`, `item_058`. Proof: the returned dict's keys were diffed against a pre-request build after every cluster - 29 keys, identical throughout, and no caller file changed.
- request-AC2 -> `item_057`. Proof: 11 closures lifted to module level in `ed1d3de`; `create_session(base_dir, env, store, name)` and `list_sessions(store)` are callable without building the service.
- request-AC3 -> `item_058`. Proof: no closure remains in the factory; every lifted function names its dependencies in its signature.
- request-AC4 -> `item_058`. Proof: `create_session_service` is 56 lines - configuration resolution, one `partial` binding, and the interface dict. No behaviour left in it.
- request-AC5 -> `item_057`, `item_058`. Proof: six commits, full suite green after each; the largest single step was one concern cluster.
- request-AC6 -> `item_059`. Proof: no file split performed. Coupling measured by transitive closure and the decision recorded with its table, including the two groups the measurement rules out as files.
- request-AC7 -> `item_058`. Proof: no test was added or rewritten; the 561 existing tests carried the whole decomposition unchanged.

# Validation
- `npm run lint` clean and 561 tests passing after each of the six commits.
- Service interface diffed against a pre-request build after every cluster: 29 keys, identical.
- `logics-manager flow validate` 0 findings; `logics-manager lint --require-status` OK.

# Report
- `create_session_service` went from 1153 lines and 46 closures to 56 lines and none. The module is now 71 flat functions, median 12 lines, largest 121.
- The interface is unchanged at 29 keys and no caller was touched, so the whole decomposition is invisible from outside the module.
- No file split was performed. The coupling measurement supports cutting `status` and `backup` out and rules out `runtime` and `auth`, which have zero exclusive helpers; that work is scoped separately.
- The recurring lesson across both this request and `req_025`: a capture or usage measurement taken once, or taken as direct calls rather than transitive, is wrong in a way that only shows up as failing tests several steps later.

# AI Context
- Summary: Orchestrate the session service decomposition
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_026_break_up_the_1153_line_session_service_factory_before_splitting_its_file`
- Product brief(s): `prod_016_a_session_service_that_can_be_read_in_pieces`
- Architecture decision(s): (none yet)
