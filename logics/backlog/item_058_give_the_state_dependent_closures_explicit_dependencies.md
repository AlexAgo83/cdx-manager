## item_058_give_the_state_dependent_closures_explicit_dependencies - Give the state-dependent closures explicit dependencies
> From version: 0.14.0
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
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
