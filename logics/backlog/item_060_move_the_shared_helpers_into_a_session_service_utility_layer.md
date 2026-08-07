## item_060_move_the_shared_helpers_into_a_session_service_utility_layer - Move the shared helpers into a session service utility layer
> From version: 0.14.0
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Low
> Theme: Maintainability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- Ten helpers are reached from more than one concern group. Extracting status or backup before relocating them would leave the new module importing back from the module it was just cut out of.
- `req_025` learned this the expensive way in the opposite order: its plan relocated shared helpers per domain, and doing all of them in one commit turned out to read far better as a diff.

# Scope
- In:
  - Relocate the ten shared helpers into a utility module, in one commit, before any group is extracted.
  - Verify afterwards that no group shares a helper with another, so the remaining extractions are independent.
  - Keep them importable from `session_service` for any caller or test that names them today.
- Out:
  - No extraction of the status or backup groups in this slice.
  - No renaming or rewriting of the helpers while moving them.
  - No relocation of helpers that only one group reaches.

# Acceptance criteria
- Every helper reached from more than one concern group has a single definition in the utility layer.
- Re-running the coupling measurement afterwards reports zero shared helpers between the remaining groups.
- No helper gains a dependency the utility layer did not already have, and no import cycle is introduced.
- The full suite passes and the service interface is unchanged.

# AC Traceability
- request-AC2 -> This backlog slice. Proof: Every helper reached from more than one concern group has a single definition in the utility layer.
- request-AC3 -> This backlog slice. Proof: Re-running the coupling measurement afterwards reports zero shared helpers between the remaining groups.
- request-AC7 -> This backlog slice. Proof: No helper gains a dependency the utility layer did not already have, and no import cycle is introduced.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_017_a_session_service_whose_file_boundaries_match_its_real_seams`
- Architecture decision(s): (none yet)
- Request: `req_027_split_session_service_along_the_two_seams_the_coupling_measurement_supports`
- Primary task(s): `task_038_orchestrate_the_measured_session_service_file_split`

# AI Context
- Summary: Move the shared helpers into a session service utility layer
- Keywords: scaffolded-backlog, move the shared helpers into a session service utility layer, implementation-ready
- Use when: Implementing the scaffolded slice for Move the shared helpers into a session service utility layer.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
