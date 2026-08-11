## item_089_unify_tray_alert_marker_and_recent_alert_read_state - Unify tray alert marker and recent-alert read state
> From version: 0.18.4
> Schema version: 1.0
> Status: Ready
> Understanding: 96%
> Confidence: 92%
> Progress: 0%
> Complexity: Medium
> Theme: Tray usability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: Unify tray alert marker and recent-alert read state
- Keywords: scaffolded-backlog, unify tray alert marker and recent-alert read state, implementation-ready
- Use when: Implementing the scaffolded slice for Unify tray alert marker and recent-alert read state.
- Skip when: The change belongs to another backlog slice.

# Problem
- A 45-second marker and process-lifetime history represent separate concepts, so users cannot tell whether a badge means new information or merely a recently delivered event.
- Clearing history when an OS toast is delivered would lose alerts the user never saw, while clearing it at menu construction would make the current consultation empty.

# Scope
- In:
  - Introduce one volatile unread-alert state in the tray runner and derive the marker and recent-alert section from it.
  - Capture the menu consultation boundary in every native backend: preserve the currently rendered unread list during the open menu, clear it for the next opening, and retain events arriving after the boundary.
  - Keep spool delivery acknowledgement and UI read acknowledgement distinct, with no new CDX command or persisted read marker.
  - Add focused platform-neutral state tests and backend lifecycle coverage where native callback handling differs.
- Out:
  - Persistent notification history, manual clear controls, badge preferences, toast interaction tracking, or changes to event delivery and acknowledgement.
  - Provider-specific hooks, remote notifications, telemetry, tray update behavior, or capacity-menu changes.

# Acceptance criteria
- AC1: Badge and menu derive from exactly the same unread items before, during, and after a consultation.
- AC2: A menu consultation clears only the alerts present at open time; later arrivals remain unread.
- AC3: Delivery durability remains unchanged and all relevant Rust tests pass.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: Badge and menu derive from exactly the same unread items before, during, and after a consultation.
- request-AC2 -> This backlog slice. Proof: AC2: A menu consultation clears only the alerts present at open time; later arrivals remain unread.
- request-AC3 -> This backlog slice. Proof: AC3: Delivery durability remains unchanged and all relevant Rust tests pass.
- request-AC4 -> This backlog slice. Proof: AC3: Delivery durability remains unchanged and all relevant Rust tests pass.
- request-AC5 -> This backlog slice. Proof: AC3: Delivery durability remains unchanged and all relevant Rust tests pass.
- request-AC6 -> This backlog slice. Proof: AC3: Delivery durability remains unchanged and all relevant Rust tests pass.

# Decision framing
- Product framing: Not needed
- Architecture framing: Settled in `adr_006_tray_menu_lifecycle_observation_boundary`: opening is the only reading event, closing is not modelled, and an unavailable signal never clears.

# Links
- Product brief(s): `prod_031_coherent_cdx_tray_unread_alerts`
- Architecture decision(s): `adr_006_tray_menu_lifecycle_observation_boundary`
- Request: `req_042_synchronize_cdx_tray_alert_badges_with_menu_reading`
- Primary task(s): `task_053_orchestrate_coherent_cdx_tray_alert_read_state`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
