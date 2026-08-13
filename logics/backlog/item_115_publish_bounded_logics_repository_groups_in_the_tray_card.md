## item_115_publish_bounded_logics_repository_groups_in_the_tray_card - Publish bounded Logics repository groups in the tray card
> From version: 0.18.6
> Schema version: 1.0
> Status: In progress
> Understanding: 95%
> Confidence: 90%
> Progress: 80%
> Complexity: Medium
> Theme: Tray data contract
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: Publish bounded repository-owned Logics groups with stable roots and collision-safe labels.
- Keywords: publish, bounded, logics, repository, groups, tray, card
- Use when: Changing Logics adapter output, card schema, or repository group labels.
- Skip when: Changing native menu rendering alone.

# Problem
- The adapter discovers multiple roots but discards all but one selected card, and flat plugin rows cannot represent ownership by repository without encoding it into display text.
- A naive expansion risks an unbounded menu or action targets reconstructed from labels.

# Scope
- In:
  - Build deterministic, bounded repository groups from the existing per-root status payloads, retaining one blocked and one next row per group when present.
  - Add an optional grouped-card snapshot field with explicit group label, validated rows, and repository roots carried only as structured action data.
  - Derive collision-safe labels from the shortest necessary parent context, with roots remaining structured focus data rather than display identity.
  - Keep the existing summary and card-wide Open Logics and Refresh Logics actions.
- Out:
  - Changing Logics manager selection rules, showing every document, or introducing arbitrary plugin-provided menu structure.

# Acceptance criteria
- AC1: Multiple active roots produce separate bounded groups with deterministic order.
- AC2: A group contains only its own blocked and next rows, each with a valid focus action and root.
- AC3: Legacy flat cards remain valid snapshot input.
- AC4: Same-basename roots receive deterministic distinct labels without exposing arbitrary absolute paths.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: Multiple active roots produce separate bounded groups with deterministic order.
- request-AC2 -> This backlog slice. Proof: AC2: A group contains only its own blocked and next rows, each with a valid focus action and root.
- request-AC3 -> This backlog slice. Proof: AC3: Legacy flat cards remain valid snapshot input.
- request-AC4 -> This backlog slice. Proof: AC3: Legacy flat cards remain valid snapshot input.
- request-AC5 -> This backlog slice. Proof: AC3: Legacy flat cards remain valid snapshot input.
- request-AC6 -> This backlog slice. Proof: AC3: Legacy flat cards remain valid snapshot input.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_045_repository_oriented_logics_tray_navigation`
- Architecture decision(s): (none yet)
- Request: `req_058_group_logics_tray_next_actions_by_repository`
- Primary task(s): `task_069_orchestrate_repository_grouped_logics_tray_navigation`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
