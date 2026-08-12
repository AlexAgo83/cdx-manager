## item_111_request_and_persist_provider_hook_consent_at_interactive_launch - Request and persist provider-hook consent at interactive launch
> From version: 0.18.6
> Schema version: 1.0
> Status: Ready
> Understanding: 95%
> Confidence: 90%
> Progress: 0%
> Complexity: Medium
> Theme: Notification consent
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: Persist one explicit installation consent before provisioning provider hooks for future profile launches.
- Keywords: request, persist, provider, hook, consent, interactive, launch
- Use when: Changing interactive hook consent, profile provisioning, or non-interactive launch behavior.
- Skip when: Changing delivery-time mute behavior after a hook already exists.

# Problem
- A per-session notify setting currently controls hook provisioning, so the user cannot tell whether tray silence means muted delivery or no hook exists to receive future changes.
- Provider hook configuration is sensitive and must be changed only after an explicit, visible operator decision.

# Scope
- In:
  - Define one persisted consent state for supported provider hooks and prompt at the eligible interactive launch boundary when it is absent.
  - Use the existing safe provisioning/removal ownership rules and preserve all non-CDX hook entries.
  - Start global alert delivery muted after consent and surface consent-required, muted, and enabled states through the existing tray/CLI status surfaces.
  - Treat consent as installation-wide while provisioning hook files per supported profile only on that profile's next eligible interactive launch.
- Out:
  - Installing hooks without consent, prompting in JSON or non-interactive runs, or changing unrelated session launch preferences.

# Acceptance criteria
- AC1: A first eligible interactive launch asks before provider hook configuration changes; decline is a no-op.
- AC2: Acceptance provisions only supported sessions through the existing provider-safe paths and persists consent for later launches.
- AC3: The resulting status clearly separates consent required from globally muted delivery.
- AC4: Accepted consent is not re-prompted for each new profile, and an already-running provider is never modified retroactively.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: A first eligible interactive launch asks before provider hook configuration changes; decline is a no-op.
- request-AC2 -> This backlog slice. Proof: AC2: Acceptance provisions only supported sessions through the existing provider-safe paths and persists consent for later launches.
- request-AC5 -> This backlog slice. Proof: AC3: The resulting status clearly separates consent required from globally muted delivery.
- request-AC6 -> This backlog slice. Proof: AC3: The resulting status clearly separates consent required from globally muted delivery.

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
