## item_105_focus_the_originating_terminal_from_a_tray_alert_row - Focus the originating terminal from a tray alert row
> From version: 0.18.6
> Schema version: 1.0
> Status: In progress
> Understanding: 95%
> Confidence: 90%
> Progress: 10%
> Complexity: High
> Theme: tray-companion
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: Focus an alert's retained terminal target only when it remains valid, otherwise state that it is unavailable.
- Keywords: focus, originating, terminal, tray, alert, row
- Use when: Adding terminal focus actions or platform-specific focus adapters.
- Skip when: Changing the terminal selected for a new tray session.

# Problem
- The operator reads which session needs them and then has to find its window among many.
- No focus mechanism is universal: each terminal, and each platform, offers a different one or none at all.
- An action that silently does nothing is indistinguishable from a broken build.

# Scope
- In:
  - Add a focus action to alert rows carrying a usable identity, dispatched by the platform backend.
  - Implement the macOS path against iTerm2 first, matching the published session identifier and activating it.
  - Probe Terminal.app and decide from evidence whether an identifier can be matched, rather than assuming parity.
  - Render the action as unavailable, with its reason, where the identity is missing or the platform offers no mechanism — the first real user of Availability::Unavailable.
  - Treat a target that no longer exists as a no-op, never as a reason to activate something else.
  - Re-validate the allowlisted identity when the retained alert is clicked; never reconstruct a launcher input from display text or the environment.
- Out:
  - Windows Terminal tab activation and Wayland window raising, neither of which the platform supports.
  - Notification-banner activation, which is its own item.
  - Bundling a terminal remote-control tool the user has not enabled.

# Acceptance criteria
- AC1: An alert carrying an iTerm2 identity focuses that session and brings the application forward when its row is activated.
- AC2: A stale, unknown or unmatchable identity results in no visible change, and never focuses another window.
- AC3: An alert with no identity, or on a platform with no mechanism, draws the action disabled with a reason the operator can read.
- AC4: Terminal.app is either supported or documented as unsupported with the evidence, not left unstated.
- AC5: Menu tests cover the available, unavailable and stale renderings, and the macOS focus path is exercised by the smoke script rather than asserted.
- AC6: Any macOS authorization the mechanism requires is documented, including what an operator sees the first time.
- AC7: A malformed identity or a target that disappeared after alert receipt is unavailable or a no-op, and cannot focus a session row, preferred terminal, or recency match.

# AC Traceability
- request-AC2 -> This backlog slice. Proof: AC1: An alert carrying an iTerm2 identity focuses that session and brings the application forward when its row is activated.
- request-AC3 -> This backlog slice. Proof: AC2: A stale, unknown or unmatchable identity results in no visible change, and never focuses another window.
- request-AC4 -> This backlog slice. Proof: AC3: An alert with no identity, or on a platform with no mechanism, draws the action disabled with a reason the operator can read.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_040_alerts_that_lead_back_to_their_terminal`
- Architecture decision(s): (none yet)
- Request: `req_053_bring_back_the_terminal_an_alert_came_from`
- Primary task(s): `task_064_deliver_alerts_that_lead_back_to_their_terminal`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
