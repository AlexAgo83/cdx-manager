## req_056_make_tray_agent_alert_muting_live_and_hook_consent_explicit_at_launch - Make tray agent-alert muting live and hook consent explicit at launch
> From version: 0.18.6
> Schema version: 1.0
> Status: Draft
> Understanding: 95%
> Confidence: 90%
> Complexity: Medium
> Theme: Interactive agent alerts
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: Live agent-alert delivery is governed by one persisted switch for tray, CLI, hook, and direct paths.
- Keywords: live mute, hook consent, profile provisioning, direct alert path
- Use when: Changing notification delivery, interactive consent, or provider hook provisioning.
- Skip when: Changing only tray presentation without affecting alert delivery.

# Needs
- Turning Agent alerts off from the tray must immediately silence desktop banners from already-running agent sessions, without waiting for a relaunch or restart.
- The product currently mixes provider-hook installation, per-session notification opt-in, and the temporary tray mute. A hook that inherited CDX_NOTIFY=0 can never observe a later tray unmute, while a hook pointed at a stale executable can bypass the intended mute state.
- Writing provider hooks, especially the Codex plugin requiring approval, needs explicit consent. That consent should be requested during an eligible interactive launch, not inferred from a tray toggle or hidden per-session setting.

# Context
- Provider hooks call cdx notify as a child process. The delivery boundary in handle_notify can read shared CDX state on every event, so it is the correct place for a live global mute; it must apply whether a tray heartbeat is present or direct desktop delivery is used.
- Hook installation is a separate persistent permission because it writes provider-owned configuration. After permission is granted, the hook must remain available while global alert delivery defaults to muted, allowing a later tray unmute to take effect for the next event without restarting the provider.
- The launch environment currently uses CDX_NOTIFY as a per-session suppression gate before compose_notification. The new contract must not leave a stale launch-time environment value able to override the shared live mute state for an installed hook.
- Existing user-owned hook entries and unsupported providers must remain untouched. The tray must distinguish hooks not yet authorised from hooks installed but globally muted.
- Consent is installation-wide, but hook files live in each supported session profile. Accepting consent authorises provisioning on the current and each later eligible session launch; it cannot retroactively add a hook to an already-running provider, and the prompt must not repeat merely because a new profile needs its first hook.
- `cdx tray alerts on|off|status` remains the global delivery control with or without a running tray. With no fresh heartbeat, enabled delivery falls back directly to the desktop channel; muted delivery still suppresses it.
- The implementation must inspect the installed provider hook cache and the absolute cdx executable it invokes. Repository tests alone cannot prove that an existing provider process reaches the live shared mute state.

# Acceptance criteria
- AC1: At an eligible interactive launch with no recorded hook-installation consent, CDX asks once before modifying provider hook configuration; declining leaves provider configuration untouched and starts no notification integration.
- AC2: After explicit consent, supported sessions receive the maintained cdx notification hook through the existing provider-safe provisioning path, while global alert delivery starts muted unless the operator explicitly turns it on.
- AC3: Toggling Agent alerts off from the running tray prevents the next event from every already-hooked supported session from raising a desktop banner immediately, while still recording it for the tray; toggling on restores delivery for the next event without a session restart.
- AC4: The live shared alert state, not a stale CDX_NOTIFY value inherited when a provider launched, is the final delivery authority for installed hooks on both tray and direct-delivery paths.
- AC5: The tray and CLI report distinct actionable states for hook consent required, hooks available but muted, and alerts enabled; unsupported providers and unrelated per-session launch settings preserve their current behaviour.
- AC6: Focused tests cover consent accept/decline, existing-hook migration compatibility, immediate mute/unmute for a launched hook environment, tray-event retention, direct delivery, and no unintended provider-config writes; project and Logics validation pass.
- AC7: One accepted installation-wide consent provisions each supported profile only on its own subsequent eligible interactive launch, never modifies a running provider, and never repeats the consent prompt solely for a new profile.
- AC8: `cdx tray alerts on|off|status` has the same live delivery semantics with no tray heartbeat: off suppresses direct banners and on restores the next direct delivery.
- AC9: macOS verification inspects and exercises the actual cached Codex or Claude hook command and its resolved executable, proving an already-running hook observes mute then unmute without a provider restart.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_043_live_tray_control_for_consented_agent_alerts`
- Architecture decision(s): (none yet)

# References
- src/agent_notify.py
- src/tray_alerts.py
- src/tray_defaults.py
- src/commands/launch.py
- src/commands/tray.py
- src/provider_runtime.py
- test/test_agent_notify_py.py
- test/test_tray_events_py.py

# Backlog
- `item_111_request_and_persist_provider_hook_consent_at_interactive_launch`
- `item_112_make_the_tray_alert_switch_the_live_delivery_authority`
