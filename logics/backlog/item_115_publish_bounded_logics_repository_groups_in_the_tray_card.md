## item_115_publish_bounded_logics_repository_groups_in_the_tray_card - Publish bounded Logics repository groups in the tray card
> From version: 0.18.6
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Tray data contract
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: publish, bounded, logics, repository, groups, tray, card
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- The adapter discovers multiple roots but discards all but one selected card, and flat plugin rows cannot represent ownership by repository without encoding it into display text.
- A naive expansion risks an unbounded menu or action targets reconstructed from labels.

# Scope
- In:
  - Build deterministic, bounded repository groups from the existing per-root status payloads, retaining one blocked and one next row per group when present.
  - Add an optional grouped-card snapshot field with explicit group label, validated rows, and repository roots carried only as structured action data.
  - Keep the existing summary and card-wide Open Logics and Refresh Logics actions.
- Out:
  - Changing Logics manager selection rules, showing every document, or introducing arbitrary plugin-provided menu structure.

# Acceptance criteria
- AC1: Multiple active roots produce separate bounded groups with deterministic order.
- AC2: A group contains only its own blocked and next rows, each with a valid focus action and root.
- AC3: Legacy flat cards remain valid snapshot input.

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
