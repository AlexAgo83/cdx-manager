## item_058_give_the_state_dependent_closures_explicit_dependencies - Give the state-dependent closures explicit dependencies
> From version: 0.14.0
> Schema version: 1.0
> Status: Done
> Understanding: 100%
> Confidence: 100%
> Progress: 100%
> Complexity: High
> Theme: Maintainability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- The remaining closures capture factory locals such as the base directory, the store, and cached state, so their dependencies are invisible at the call site and they cannot be exercised in isolation.
- This is what actually keeps the factory at four figures, and what makes any file split premature.

# Scope
- In:
  - For each remaining closure, determine exactly what it captures and pass that explicitly instead, keeping the returned dict as the binding layer.
  - Group the extractions by the concern clusters the closures already fall into — session CRUD, backup and bundles, status, launch and history, auth — so each commit is one readable theme.
  - Prefer passing the few values a function actually needs over passing a context object, so the signature stays informative.
  - Leave `create_session_service` as assembly: resolving configuration, constructing the store, and binding the interface.
  - Add tests only where an extraction newly makes something directly testable, rather than restating coverage the existing suite already provides through the interface.
  - Run the full suite after each commit.
- Out:
  - No interface change and no caller change.
  - No file split.
  - No service class or injection framework.
  - No rewriting of existing tests to the new shape.

# Acceptance criteria
- No closure in `create_session_service` captures factory state implicitly; dependencies appear in signatures.
- `create_session_service` contains assembly and binding, not behavior.
- The returned dict has the same keys and behavior as before the request.
- Session-service behavior can be exercised without constructing the whole service.
- The full suite passes after each commit, and existing test bodies are unchanged.
- The remaining factory is materially smaller than 1153 lines, with the figure recorded at closeout.

# Outcome

`create_session_service` is **56 lines** and contains no closures: it resolves
configuration, binds `fetch_codex_status` once, and returns the interface
dict. Down from 1153 lines and 46 closures. The returned dict is unchanged at
29 keys, no caller was touched, and 561 tests pass after every commit.

Delivered in five commits by concern cluster: settings and auth (`b2a1f0d`
lineage), session CRUD (`7516d35`), runtime/launch/history, status, and
status-rows/backup (`a0455f3`).

Session-service behaviour is now exercisable without building the service -
`create_session(base_dir, env, store, name)` and `list_sessions(store)` work
directly - which is what AC4 asked for.

Four things worth recording, because each cost a test failure to find:

- **Capture measurements expire.** Making a callee explicit adds its
  dependencies to every caller, so the measured capture set is valid only for
  the very next lift. Taking it once at the start and working through a batch
  produced 27 then 76 failures; re-measuring between lifts is the working
  method.
- **Lifting must go callee-before-caller.** A driver that picked the closure
  with the fewest dependencies first was not a topological order and lifted
  `get_status_rows` before `_resolve_row_session`.
- **The interface key is not always the function name.**
  `_session_runtime` is bound as `active_session_runtime`, so the binding was
  left pointing at the bare function and handed callers something short of its
  first argument. 27 tests caught it; the transform now refuses to finish
  while any binding still points at a bare lifted function.
- **A bare function reference is not a call.**
  `executor.submit(_resolve_row_session, ...)` passes the function rather
  than calling it, so no call-site rewrite applied. Its dependencies go
  through `submit`'s own argument forwarding.

One deliberate departure from the letter of the scope. `_resolve_session_status`
measured six captured locals, which prepended to its five existing parameters
would have given an eleven-parameter signature - the opposite of the
informative signature this slice is for. Three of the six existed only to call
`_fetch_codex_status`, so the factory binds that once and passes the callable:
four dependencies instead of six. That function also tested
`codex_status_fetcher` for presence rather than only calling through it, so
the binding is `None` when there is no fetcher and the guard tests the
callable.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: No closure in `create_session_service` captures factory state implicitly; dependencies appear in signatures.
- request-AC3 -> This backlog slice. Proof: `create_session_service` contains assembly and binding, not behavior.
- request-AC4 -> This backlog slice. Proof: The returned dict has the same keys and behavior as before the request.
- request-AC5 -> This backlog slice. Proof: Session-service behavior can be exercised without constructing the whole service.
- request-AC7 -> This backlog slice. Proof: The full suite passes after each commit, and existing test bodies are unchanged.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_016_a_session_service_that_can_be_read_in_pieces`
- Architecture decision(s): (none yet)
- Request: `req_026_break_up_the_1153_line_session_service_factory_before_splitting_its_file`
- Primary task(s): `task_037_orchestrate_the_session_service_decomposition`

# AI Context
- Summary: Give the state-dependent closures explicit dependencies
- Keywords: scaffolded-backlog, give the state-dependent closures explicit dependencies, implementation-ready
- Use when: Implementing the scaffolded slice for Give the state-dependent closures explicit dependencies.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
