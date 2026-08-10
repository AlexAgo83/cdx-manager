## item_082_deliver_agent_hook_events_through_the_active_cdx_tray_with_safe_fallback - Deliver agent hook events through the active CDX tray with safe fallback
> From version: 0.17.1
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: High
> Theme: Desktop integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-10 22:05:55

# AI Context
- Summary: Deliver agent hook events through the active CDX tray with safe fallback
- Keywords: scaffolded-backlog, deliver agent hook events through the active cdx tray with safe fallback, implementation-ready
- Use when: Implementing the scaffolded slice for Deliver agent hook events through the active CDX tray with safe fallback.
- Skip when: The change belongs to another backlog slice.

# Problem
- Direct hook notifications and an active tray would otherwise create duplicate toasts and leave no durable in-tray signal.
- A cross-process notification handoff must remain best-effort: a provider hook cannot wait on a GUI, and WSL networking cannot be assumed symmetric.
- A polled spool trades latency for portability, and an unbounded poll across wsl.exe keeps the WSL VM permanently awake, so both the delay and the idle cost need explicit limits.

# Scope
- In:
  - Add a small versioned local event-spool and heartbeat protocol beneath the existing composed-notification boundary.
  - Have cdx notify choose tray publication only for a fresh compatible heartbeat, otherwise retain the existing direct notification dispatch unchanged.
  - Have the installed tray consume and acknowledge events once, show a temporary icon hint plus a bounded menu history, and emit one native local notification when its capability is available.
  - Create the Windows Start Menu shortcut carrying the AppUserModelID and its stub CLSID, and register the AUMID. Moved here from item_080 on purpose: its only function is to make a toast reach Action Center, so building it before there is a toast would be work nobody could verify. It lands with the first notification, where it either works or does not.
  - Bridge Windows-hosted WSL through explicit wsl.exe reads and writes of CDX-controlled state rather than sockets, ports, or GUI forwarding.
  - Bound the consumption loop to the adr_005 poll budget, stop it when no session is enabled, back it off after repeated read failures, and size the heartbeat freshness window wider than one poll period.
  - Reuse existing privacy normalization and preference checks; add focused unit and integration-boundary coverage plus documentation.
- Out:
  - Changing provider hook schemas, notification opt-in defaults, quota status collection, or the normal cdx status output.
  - Network listeners, push-notification providers, external services, remote desktops, or cross-machine delivery.
  - Persistent notification archives, searchable history, custom notification templates, or automatic tray startup.
  - Implementing the base tray companion itself; req_035 remains the prerequisite.

# Acceptance criteria
- AC1: A fresh active tray receives one sanitized event and becomes the sole visible notification owner; an absent or stale tray leaves the existing direct path intact.
- AC2: Events are bounded, user-private, idempotently acknowledged, and safe under partial or malformed local state.
- AC3: The tray exposes a clear short-lived hint and recent-event menu state for completion and attention without exposing preview text unless opted in.
- AC4: The Windows host to WSL bridge uses explicit interop commands and has no localhost, port-forwarding, or Linux-GUI prerequisite.
- AC5: Platform capability failure and user notification permission denial avoid duplicate direct notifications while retaining a tray-visible event state.
- AC6: Alert latency is at most one poll period, the loop stops when no session is enabled, backs off after repeated failures, and the heartbeat window exceeds one poll period so a live tray is never read as stale.
- AC7: macOS notifications are emitted from the signed CDX bundle and carry the CDX icon and name; a refused, revoked, or unavailable authorization falls back to osascript delivery without a duplicate, and the authorization state is reportable.
- AC8: Focused tests, existing notification tests, tray-boundary smoke checks, and full project validation pass.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: A fresh active tray receives one sanitized event and becomes the sole visible notification owner; an absent or stale tray leaves the existing direct path intact.
- request-AC2 -> This backlog slice. Proof: AC2: Events are bounded, user-private, idempotently acknowledged, and safe under partial or malformed local state.
- request-AC3 -> This backlog slice. Proof: AC3: The tray exposes a clear short-lived hint and recent-event menu state for completion and attention without exposing preview text unless opted in.
- request-AC4 -> This backlog slice. Proof: AC4: The Windows host to WSL bridge uses explicit interop commands and has no localhost, port-forwarding, or Linux-GUI prerequisite.
- request-AC5 -> This backlog slice. Proof: AC5: Platform capability failure and user notification permission denial avoid duplicate direct notifications while retaining a tray-visible event state.
- request-AC6 -> This backlog slice. Proof: AC4: The Windows host to WSL bridge uses explicit interop commands and has no localhost, port-forwarding, or Linux-GUI prerequisite.
- request-AC7 -> This backlog slice. Proof: AC5: Platform capability failure and user notification permission denial avoid duplicate direct notifications while retaining a tray-visible event state.
- request-AC9 -> This backlog slice. Proof: AC6: Alert latency is at most one poll period, the loop stops when no session is enabled, backs off after repeated failures, and the heartbeat window exceeds one poll period.
- request-AC10 -> This backlog slice. Proof: AC7: macOS notifications are emitted from the signed CDX bundle and carry the CDX icon and name; a refused, revoked, or unavailable authorization falls back to osascript delivery without a duplicate.
- request-AC8 -> This backlog slice. Proof: AC8: Focused tests, existing notification tests, tray-boundary smoke checks, and full project validation pass.

# Decision framing
- Product framing: Not needed
- Architecture framing: Settled in `adr_005_cdx_tray_runtime_and_companion_transport_boundary`

# Links
- Product brief(s): `prod_025_tray_aware_agent_alerts`
- Architecture decision(s): `adr_005_cdx_tray_runtime_and_companion_transport_boundary`
- Request: `req_036_route_cdx_agent_alerts_through_an_active_tray_companion`
- Primary task(s): `task_047_orchestrate_tray_aware_cdx_agent_alert_delivery`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
