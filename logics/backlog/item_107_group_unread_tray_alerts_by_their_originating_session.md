## item_107_group_unread_tray_alerts_by_their_originating_session - Group unread tray alerts by their originating session
> From version: 0.18.6
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 90%
> Complexity: Medium
> Theme: Tray usability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-13 00:53:55

# AI Context
- Summary: Turn the existing bounded unread list into stable session submenus while keeping the current consultation boundary and safe fallback events.
- Keywords: group, unread, tray, alerts, originating, session
- Use when: Changing Rust tray menu rendering for structured agent alerts.
- Skip when: Changing hook payloads, storage, retention, or per-alert read persistence.

# Problem
- A flat recent-alert list interleaves messages from concurrent sessions, forcing an operator to repeatedly rediscover which work stream a message belongs to.
- The current event envelope is deliberately structured, but the menu ignores its session identity for grouping.

# Scope
- In:
  - Group the existing bounded unread event list into session submenus plus one fallback group for events without a session.
  - Order groups by newest event and messages newest first, showing a count in each session group.
  - Keep existing stable session actions for session-bound messages and retain safe text-only handling for incomplete events.
  - Cover the Rust menu model and unread lifecycle with focused tests.
- Out:
  - Changing event storage, hook payloads, alert retention limits, mute policy, or the native-notification fallback.
  - Adding persistent per-alert read state, cross-device history, or an alert search interface.
  - Recovering a session identity from a rendered title, message, or menu index.

# Acceptance criteria
- AC1: Unread alerts render beneath one Alert groups heading as session submenus with counts and one fallback group when needed.
- AC2: Group and message ordering derives deterministically from the existing newest-first bounded event list.
- AC3: Session-bound alert messages retain the existing stable Session action and all incomplete events remain non-actionable text.
- AC4: Existing consultation, marker, notification, acknowledgement, and mute tests continue to pass alongside focused grouping coverage.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: Unread alerts render beneath one Alert groups heading as session submenus with counts and one fallback group when needed.
- request-AC2 -> This backlog slice. Proof: AC2: Group and message ordering derives deterministically from the existing newest-first bounded event list.
- request-AC3 -> This backlog slice. Proof: AC3: Session-bound alert messages retain the existing stable Session action and all incomplete events remain non-actionable text.
- request-AC4 -> This backlog slice. Proof: AC4: Existing consultation, marker, notification, acknowledgement, and mute tests continue to pass alongside focused grouping coverage.
- request-AC8 -> This backlog slice. Proof: AC4: Existing consultation, marker, notification, acknowledgement, and mute tests continue to pass alongside focused grouping coverage.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_041_contextual_cdx_tray_recovery_paths`
- Architecture decision(s): (none yet)
- Request: `req_054_group_tray_alerts_by_session_and_make_logics_actions_reliably_open_the_viewer`
- Primary task(s): `task_065_orchestrate_grouped_tray_alerts_and_reliable_logics_viewer_actions`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
