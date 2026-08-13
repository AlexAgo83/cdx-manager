## item_106_make_the_notification_banner_act_like_the_alert_row_on_macos - Make the notification banner act like the alert row on macOS
> From version: 0.18.6
> Schema version: 1.0
> Status: In progress
> Understanding: 95%
> Confidence: 90%
> Progress: 80%
> Complexity: Medium
> Theme: tray-companion
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: Route macOS notification-banner clicks through the same retained alert action as tray rows.
- Keywords: notification, banner, act, like, alert, row, macos
- Use when: Changing macOS notification delegates or alert click dispatch.
- Skip when: Changing terminal-origin metadata or non-macOS notifications.

# Problem
- The banner is what the operator sees first, and clicking it does nothing at all today.
- The companion sets no notification delegate, so click responses are never received.
- The osascript fallback path cannot be activated, and neither can the Windows toast the current implementation raises.

# Scope
- In:
  - Set a notification delegate on macOS so a click on a banner reaches the companion.
  - Carry the alert identity on the notification so the click resolves to the same target the row would.
  - Route the click through the same focus path as the row, so the two cannot diverge.
  - State plainly, in the module that owns it, that the fallback delivery path and the Windows toast are not activatable.
- Out:
  - Windows toast activation, which needs an AppUserModelID and a registered COM activator a non-packaged app cannot rely on.
  - Linux notification actions, pending the focus mechanism the previous item settles.
  - Any behaviour on click other than the focus the row already performs.

# Acceptance criteria
- AC1: Clicking a delivered banner on macOS focuses the same terminal the alert row would.
- AC2: The delegate is in place before any notification is delivered, so the first alert of a run is clickable like the rest.
- AC3: A banner raised through the fallback path is delivered as before, and its inability to be activated is documented rather than silently accepted.
- AC4: A click whose target has gone does nothing visible, matching the row's behaviour exactly.
- AC5: Tray tests cover the delegate wiring and the shared resolution path.

# AC Traceability
- request-AC5 -> This backlog slice. Proof: AC1: Clicking a delivered banner on macOS focuses the same terminal the alert row would.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_040_alerts_that_lead_back_to_their_terminal`
- Architecture decision(s): (none yet)
- Request: `req_053_bring_back_the_terminal_an_alert_came_from`
- Primary task(s): `task_064_deliver_alerts_that_lead_back_to_their_terminal`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
