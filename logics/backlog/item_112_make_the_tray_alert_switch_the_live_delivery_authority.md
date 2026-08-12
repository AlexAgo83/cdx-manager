## item_112_make_the_tray_alert_switch_the_live_delivery_authority - Make the tray alert switch the live delivery authority
> From version: 0.18.6
> Schema version: 1.0
> Status: Ready
> Understanding: 95%
> Confidence: 90%
> Progress: 0%
> Complexity: Medium
> Theme: Interactive notification delivery
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: Read one shared alert-delivery state at delivery time so tray and CLI muting apply immediately.
- Keywords: tray, alert, switch, live, delivery, authority
- Use when: Changing tray alert controls, CLI alert commands, hooks, or direct notification fallback.
- Skip when: Changing only hook installation consent.

# Problem
- A launch-time CDX_NOTIFY suppression value can prevent an installed hook from reaching the shared mute decision, making a tray toggle ineffective until the session restarts.
- The user needs muted events retained in tray history without allowing either the tray or direct fallback to raise a banner.

# Scope
- In:
  - Make handle_notify read one shared live alert-delivery state for every composed event and apply it before either tray-owned or direct desktop delivery.
  - Remove or migrate only the stale launch-time suppression that conflicts with the live global contract, retaining privacy preview and session identity environment fields.
  - Test the next event before and after a tray toggle using an already-hooked launch environment, including tray retention and direct fallback.
  - Verify the actual cached provider hook command and absolute cdx executable on macOS, not only a checkout-level hook fixture.
- Out:
  - Changing provider hook payload schemas, exposing transcript or tool-input data, deleting alert history on mute, or adding a new notification backend.

# Acceptance criteria
- AC1: A muted global state suppresses banners immediately for both tray and direct paths while retaining the event for the tray.
- AC2: An enabled global state restores delivery for the next event from the same launched hook environment.
- AC3: Legacy installed hooks and existing non-notification launch behaviour remain compatible.
- AC4: With no tray heartbeat, `alerts off` suppresses direct banners and `alerts on` restores the next direct delivery from the same hook environment.
- AC5: A real cached provider hook observes mute then unmute without restarting its provider.

# AC Traceability
- request-AC2 -> This backlog slice. Proof: AC1: A muted global state suppresses banners immediately for both tray and direct paths while retaining the event for the tray.
- request-AC3 -> This backlog slice. Proof: AC2: An enabled global state restores delivery for the next event from the same launched hook environment.
- request-AC4 -> This backlog slice. Proof: AC3: Legacy installed hooks and existing non-notification launch behaviour remain compatible.
- request-AC5 -> This backlog slice. Proof: AC3: Legacy installed hooks and existing non-notification launch behaviour remain compatible.
- request-AC6 -> This backlog slice. Proof: AC3: Legacy installed hooks and existing non-notification launch behaviour remain compatible.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_043_live_tray_control_for_consented_agent_alerts`
- Architecture decision(s): (none yet)
- Request: `req_056_make_tray_agent_alert_muting_live_and_hook_consent_explicit_at_launch`
- Primary task(s): `task_067_orchestrate_live_tray_muting_and_launch_time_hook_consent`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
