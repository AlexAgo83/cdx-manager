## item_057_lift_the_closures_that_capture_nothing_into_module_level_functions - Lift the closures that capture nothing into module-level functions
> From version: 0.14.0
> Schema version: 1.0
> Status: Done
> Understanding: 100%
> Confidence: 100%
> Progress: 100%
> Complexity: Medium
> Theme: Maintainability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- Some of the 46 closures are inside the factory only by position, not because they need anything from it. They are ordinary functions written in the wrong place.
- While they sit there they cannot be imported or tested directly, and they inflate the factory that everything else has to be read through.

# Scope
- In:
  - Identify which closures reference no factory local, mechanically rather than by eye.
  - Move each to module level unchanged, keeping the returned dict pointing at it so the interface is untouched.
  - Work in small commits, running the full suite after each, so a regression is attributable to one move.
  - Record how many closures this accounts for, since it sizes the harder work that follows.
- Out:
  - No closure that captures factory state.
  - No behavior change or rename.
  - No file split.
  - No new tests beyond confirming the moved functions are importable and behave identically.

# Acceptance criteria
- Every closure that references no factory local is defined at module level.
- `create_session_service` returns the same keys, bound to the same behavior.
- Each moved function is importable and callable without constructing the service.
- The full suite passes after each individual move.
- No moved function's body differs from before the move.

# Outcome

Delivered in `ed1d3de`. The factory goes 1154 -> 1014 lines and 46 -> 35
closures; the service dict is unchanged at 29 keys and no caller changed.

The slice was scoped from a count of 19 zero-capture closures. Only **11**
lift as-is. The other eight capture no factory local themselves but call a
peer closure that does, so lifting them means threading that peer through as
an argument - which is `item_058`'s job, not this one. The difference is
direct versus transitive measurement, the same distinction that changed the
shared-helper count in `req_025`.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: Every closure that references no factory local is defined at module level.
- request-AC2 -> This backlog slice. Proof: `create_session_service` returns the same keys, bound to the same behavior.
- request-AC5 -> This backlog slice. Proof: Each moved function is importable and callable without constructing the service.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_016_a_session_service_that_can_be_read_in_pieces`
- Architecture decision(s): (none yet)
- Request: `req_026_break_up_the_1153_line_session_service_factory_before_splitting_its_file`
- Primary task(s): `task_037_orchestrate_the_session_service_decomposition`

# AI Context
- Summary: Lift the closures that capture nothing into module-level functions
- Keywords: scaffolded-backlog, lift the closures that capture nothing into module-level functions, implementation-ready
- Use when: Implementing the scaffolded slice for Lift the closures that capture nothing into module-level functions.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
