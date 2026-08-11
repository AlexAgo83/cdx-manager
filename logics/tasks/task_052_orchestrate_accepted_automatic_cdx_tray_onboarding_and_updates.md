## task_052_orchestrate_accepted_automatic_cdx_tray_onboarding_and_updates - Orchestrate accepted automatic CDX tray onboarding and updates
> From version: 0.18.4
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# AI Context
- Summary: Orchestrate accepted automatic CDX tray onboarding and updates
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Trace install flags and prompts, session creation defaults, notification preference persistence, provider provisioning, companion instance detection, autostart artifacts, and update staging end to end.
- [ ] 2. Define the smallest explicit consent state and deterministic non-interactive flags; apply accepted alert intent to existing and future supported sessions while surfacing provider trust boundaries.
- [ ] 3. Implement the running-companion update transaction: identify the CDX instance, request bounded graceful shutdown, promote the verified replacement, relaunch it, and retain or restore a proven working companion on failure.
- [ ] 4. Add targeted tests for all consent and restart outcomes, update README and diagnostics, then run project and Logics validation plus native smoke checks where available.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_088_add_consented_tray_onboarding_defaults_and_safe_running_companion_restart`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_088_add_consented_tray_onboarding_defaults_and_safe_running_companion_restart`. Proof deferred to slice closeout.
- request-AC2 -> `item_088_add_consented_tray_onboarding_defaults_and_safe_running_companion_restart`. Proof deferred to slice closeout.
- request-AC3 -> `item_088_add_consented_tray_onboarding_defaults_and_safe_running_companion_restart`. Proof deferred to slice closeout.
- request-AC4 -> `item_088_add_consented_tray_onboarding_defaults_and_safe_running_companion_restart`. Proof deferred to slice closeout.
- request-AC5 -> `item_088_add_consented_tray_onboarding_defaults_and_safe_running_companion_restart`. Proof deferred to slice closeout.
- request-AC6 -> `item_088_add_consented_tray_onboarding_defaults_and_safe_running_companion_restart`. Proof deferred to slice closeout.
- request-AC7 -> `item_088_add_consented_tray_onboarding_defaults_and_safe_running_companion_restart`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_041_make_accepted_cdx_tray_onboarding_and_updates_automatic`
- Product brief(s): `prod_030_accepted_automatic_cdx_tray_experience`
- Architecture decision(s): (none yet)
