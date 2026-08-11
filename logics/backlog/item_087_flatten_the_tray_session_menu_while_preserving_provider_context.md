## item_087_flatten_the_tray_session_menu_while_preserving_provider_context - Flatten the tray session menu while preserving provider context
> From version: 0.18.4
> Schema version: 1.0
> Status: Ready
> Understanding: 95%
> Confidence: 92%
> Progress: 0%
> Complexity: Low
> Theme: Tray usability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: Flatten the tray session menu while preserving provider context
- Keywords: scaffolded-backlog, flatten the tray session menu while preserving provider context, implementation-ready
- Use when: Implementing the scaffolded slice for Flatten the tray session menu while preserving provider context.
- Skip when: The change belongs to another backlog slice.

# Problem
- Provider grouping obscures the capacity-first priority order and causes graphical macOS rows to bind to an unrelated original snapshot index when providers interleave.
- Removing headings without adding provider text would make a multi-provider list ambiguous.
- Flattening dissolves the two competing numbering schemes, but leaves a positional session action bound to a rank this slice makes depend on capacity, so a snapshot that reorders between the draw and the click opens the wrong session.

# Scope
- In:
  - Remove provider grouping from the shared menu model and keep the snapshot's global order.
  - Include the provider in every text and macOS custom session row.
  - Bind menu actions and custom cells directly to the same stable session identity.
  - Add focused Rust regression tests for the reported reordering case and preserve the existing tray menu behavior outside session rows.
- Out:
  - Changes to the source snapshot ordering, quota values, provider status refresh, or session configuration.
  - User-selectable sorting, provider filters, nested submenus, or new tray settings.
  - Changes to agent alerts, notification payloads, event history, or platform-specific tray installation.

# Acceptance criteria
- AC1: The shared menu model lists sessions exactly in snapshot order, once each, with provider text on each row.
- AC2: macOS custom cells display the same session and provider as their menu action; Windows and Linux retain accurate text rows.
- AC3: A synthetic interleaving where a Codex session moves past Claude sessions cannot display or launch the wrong session.
- AC4: Existing tray-focused tests and the smallest relevant project validation pass.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: The shared menu model lists sessions exactly in snapshot order, once each, with provider text on each row.
- request-AC2 -> This backlog slice. Proof: AC2: macOS custom cells display the same session and provider as their menu action; Windows and Linux retain accurate text rows.
- request-AC3 -> This backlog slice. Proof: AC3: A synthetic interleaving where a Codex session moves past Claude sessions cannot display or launch the wrong session.
- request-AC4 -> This backlog slice. Proof: AC4: Existing tray-focused tests and the smallest relevant project validation pass.
- request-AC5 -> This backlog slice. Proof: AC4: Existing tray-focused tests and the smallest relevant project validation pass.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_029_capacity_first_cdx_tray_menu`
- Architecture decision(s): (none yet)
- Request: `req_040_keep_the_cdx_tray_menu_globally_ordered_by_remaining_capacity`
- Primary task(s): `task_051_orchestrate_the_capacity_first_cdx_tray_session_menu`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
