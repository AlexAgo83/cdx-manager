## item_044_publish_machine_readable_schema_for_enums_and_argument_constraints - Publish machine-readable schema for enums and argument constraints
> From version: 0.12.4
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Low
> Theme: Agent integration surface
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- The valid values for `permission`, `power`/`reasoning-effort`, and `kind` exist only inside cdx's parser and inside the human usage strings, so every programmatic caller hand-copies them.
- Those copies drift silently. GitHub issue #8 mapped a permission to a provider flag that never existed in that provider's CLI, and it survived because no caller shared cdx's own definition of the permission set.
- The mutual exclusivity of a named session and `--provider` is likewise undiscoverable except by triggering it.

# Scope
- In:
  - Add a `cdx schema --json` subcommand emitting the accepted values for the constrained options, the declared mutually-exclusive argument groups, and the current `schema_version`.
  - Derive the emitted values from the same definitions the parser and provider mapping already use, so the schema cannot drift from enforcement.
  - Add a test asserting the schema and the parser agree on every constrained option, so adding a value in one place without the other fails.
  - Document the subcommand in the README as the discovery entry point for programmatic callers.
  - Note in the documentation which provider mappings are intentionally empty, so an absent mapping reads as deliberate rather than missing.
- Out:
  - No full JSON Schema or OpenAPI document for every subcommand.
  - No generated client code.
  - No versioned schema negotiation beyond the existing `schema_version` field.
  - No change to how permissions are mapped to provider flags.

# Acceptance criteria
- `cdx schema --json` returns the accepted values for `permission`, `power`/`reasoning-effort`, and `kind`, and declares the session-and-provider mutual exclusion.
- A test fails if a value accepted by the argument parser for a constrained option is absent from the schema output, or the reverse.
- The emitted values match the parser's accepted values exactly for every constrained option, with no separately maintained list introduced by this item.
- The README documents `cdx schema --json` as the way a programmatic caller discovers valid values instead of copying them.
- The command requires `--json` consistently with the other machine-facing subcommands.

# AC Traceability
- request-AC5 -> This backlog slice. Proof: `cdx schema --json` returns the accepted values for `permission`, `power`/`reasoning-effort`, and `kind`, and declares the session-and-provider mutual exclusion.
- request-AC9 -> This backlog slice. Proof: A test fails if a value accepted by the argument parser for a constrained option is absent from the schema output, or the reverse.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_011_programmatic_cli_contract_for_non_interactive_callers`
- Architecture decision(s): (none yet)
- Request: `req_021_close_the_programmatic_cli_contract_gaps_that_force_agent_callers_to_reimplement_cdx_internals`
- Primary task(s): `task_032_orchestrate_the_programmatic_cli_contract_for_agent_callers`

# AI Context
- Summary: Publish machine-readable schema for enums and argument constraints
- Keywords: scaffolded-backlog, publish machine-readable schema for enums and argument constraints, implementation-ready
- Use when: Implementing the scaffolded slice for Publish machine-readable schema for enums and argument constraints.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
