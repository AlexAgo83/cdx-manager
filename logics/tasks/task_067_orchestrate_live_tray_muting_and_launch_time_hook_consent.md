## task_067_orchestrate_live_tray_muting_and_launch_time_hook_consent - Orchestrate live tray muting and launch-time hook consent
> From version: 0.18.6
> Schema version: 1.0
> Status: In progress
> Understanding: 100%
> Confidence: 95%
> Progress: 55%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Owner: Codex

# AI Context
- Summary: Deliver live muting backed by one delivery state, with explicit consent before hooks are provisioned.
- Keywords: alert mute, hook consent, provider profile, direct fallback
- Use when: Implementing notification consent, live muting, or hook delivery behavior.
- Skip when: Changing only unread-alert presentation.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Trace the exact active hook command, inherited notification environment, and shared tray-state path before changing any delivery gate.
- [x] 2. Add the smallest explicit consent record and interactive launch prompt, preserving non-interactive and unsupported-provider paths.
- [x] 3. Make the shared mute state authoritative at hook delivery time and prove an already-launched hook responds to off then on without restarting its provider.
- [x] 4. Update tray/CLI state wording, validate preservation of tray history and direct fallback, and record the real hook/executable smoke evidence before closeout.
- [x] 5. Separate installation-wide consent from per-profile hook provisioning; prove the no-tray direct path and the installed cached-hook path both observe the same live state.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_111_request_and_persist_provider_hook_consent_at_interactive_launch`
- `item_112_make_the_tray_alert_switch_the_live_delivery_authority`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_111_request_and_persist_provider_hook_consent_at_interactive_launch`. Proof deferred to slice closeout.
- request-AC2 -> `item_111_request_and_persist_provider_hook_consent_at_interactive_launch`. Proof deferred to slice closeout.
- request-AC5 -> `item_111_request_and_persist_provider_hook_consent_at_interactive_launch`. Proof deferred to slice closeout.
- request-AC6 -> `item_111_request_and_persist_provider_hook_consent_at_interactive_launch`. Proof deferred to slice closeout.
- request-AC2 -> `item_112_make_the_tray_alert_switch_the_live_delivery_authority`. Proof deferred to slice closeout.
- request-AC3 -> `item_112_make_the_tray_alert_switch_the_live_delivery_authority`. Proof deferred to slice closeout.
- request-AC4 -> `item_112_make_the_tray_alert_switch_the_live_delivery_authority`. Proof deferred to slice closeout.
- request-AC5 -> `item_112_make_the_tray_alert_switch_the_live_delivery_authority`. Proof deferred to slice closeout.
- request-AC6 -> `item_112_make_the_tray_alert_switch_the_live_delivery_authority`. Proof deferred to slice closeout.
- request-AC7 -> `item_111_request_and_persist_provider_hook_consent_at_interactive_launch`. Proof deferred to slice closeout.
- request-AC8 -> `item_112_make_the_tray_alert_switch_the_live_delivery_authority`. Proof deferred to slice closeout.
- request-AC9 -> `item_112_make_the_tray_alert_switch_the_live_delivery_authority`. Proof deferred to slice closeout.
- request-AC1 -> This task. Proof: 4c49a48 and `test_launch_notifications_py.py` prove interactive accept and decline behavior.
- request-AC2 -> This task. Proof: 4c49a48 and the full Python suite prove consent-backed supported-provider provisioning.
- request-AC3 -> This task. Proof: 3dbe8a1 and `test_tray_events_py.py` prove the next event observes mute then unmute.
- request-AC4 -> This task. Proof: 3dbe8a1 proves legacy `CDX_NOTIFY=0` cannot override shared alert state.
- request-AC5 -> This task. Proof: 4c49a48 starts consented delivery muted; 3dbe8a1 preserves live CLI/tray control.
- request-AC6 -> This task. Proof: full Python suite and `npm run lint` passed.
- request-AC7 -> This task. Proof: `test_launch_notifications_py.py` proves per-profile next-launch provisioning without a repeat prompt.
- request-AC8 -> This task. Proof: `cdx tray alerts off|status|on --json` was exercised without changing tray lifecycle.
- request-AC9 -> This task. Proof: inspected cached work1 Codex hook and resolved `/Users/alexandreagostini/.local/bin/cdx` executable.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_056_make_tray_agent_alert_muting_live_and_hook_consent_explicit_at_launch`
- Product brief(s): `prod_043_live_tray_control_for_consented_agent_alerts`
- Architecture decision(s): (none yet)
