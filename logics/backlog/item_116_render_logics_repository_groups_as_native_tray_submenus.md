## item_116_render_logics_repository_groups_as_native_tray_submenus - Render Logics repository groups as native tray submenus
> From version: 0.18.6
> Schema version: 1.0
> Status: In progress
> Understanding: 95%
> Confidence: 90%
> Progress: 10%
> Complexity: Medium
> Theme: Tray interaction
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: Render repository groups as bounded native tray submenus without losing stable action targets.
- Keywords: render, logics, repository, groups, native, tray, submenus
- Use when: Changing Rust companion menu parsing, submenu construction, or group action dispatch.
- Skip when: Changing card discovery or repository label selection.

# Problem
- The Rust companion currently maps every plugin row directly to one action row, so repository ownership cannot be navigated as a submenu.

# Scope
- In:
  - Parse and bound optional repository groups alongside legacy rows, then render at most five groups with at most two rows each as native submenus below the Logics summary.
  - Forward each grouped action and root verbatim through the established Plugin action path.
  - Add Rust menu and snapshot tests for subgroup labels, actions, compatibility, and malformed input.
- Out:
  - A generic nested plugin marketplace, action execution inside the companion, or changing the platform-specific action runner.

# Acceptance criteria
- AC1: Each repository appears as one submenu whose child labels are concise blocked/next actions.
- AC2: Clicking a child passes its original action and root to CDX.
- AC3: Flat legacy rows and card-wide actions retain their current rendering.
- AC4: A minor-schema-compatible parser accepts older flat cards, older companions ignore groups safely, and malformed or excess groups cannot reach the native menu.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: Each repository appears as one submenu whose child labels are concise blocked/next actions.
- request-AC2 -> This backlog slice. Proof: AC2: Clicking a child passes its original action and root to CDX.
- request-AC3 -> This backlog slice. Proof: AC3: Flat legacy rows and card-wide actions retain their current rendering.
- request-AC4 -> This backlog slice. Proof: AC3: Flat legacy rows and card-wide actions retain their current rendering.
- request-AC5 -> This backlog slice. Proof: AC3: Flat legacy rows and card-wide actions retain their current rendering.
- request-AC6 -> This backlog slice. Proof: AC3: Flat legacy rows and card-wide actions retain their current rendering.

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
