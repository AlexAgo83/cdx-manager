## task_041_orchestrate_agent_completion_notifications - Orchestrate agent completion notifications
> From version: 0.15.1
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-09 17:33:18

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Confirm which events each provider actually reports and what payload it passes — Claude Code's `Stop` and `Notification` hooks, Codex's `notify` key — since the message wording and the event distinction depend on what is really available rather than on what is documented.
- [ ] 2. Retire the `--at-reset`/`--next-ready` parsing and README rows first, checking that `cdx ready` and its scheduling path are untouched, so the name is free before anything is built on it.
- [ ] 3. Build `cdx notify` as the hook target over the existing `send_desktop_notification`, including the resolution of the session name from the launch environment and the swallow-everything failure behavior.
- [ ] 4. Add the idempotent provisioning and revocation into the launch path, marking cdx's own entries so they can be recognized and removed without touching user-authored ones.
- [ ] 5. Add the `--notify on|off` launch setting alongside the existing on/off settings, defaulting to on.
- [ ] 6. Verify the end-to-end case the request exists for: two sessions launched in two different repositories, each producing a notification that names itself.
- [ ] 7. Check the failure paths deliberately — no notifier binary, unreadable configuration, malformed payload — confirming none of them reaches the user as a launch or turn error.
- [ ] 8. Update the README's notification and command-reference sections, and reconcile the `cdx ready` description that currently refers to `cdx notify`.
- [ ] 9. Run the notify and CLI test files, then `logics-manager lint --require-status` and `logics-manager audit --group-by-doc` before closeout.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_073_reassign_cdx_notify_to_the_agent_event_hook_target`
- `item_074_provision_and_revoke_provider_hooks_in_each_session_s_home_at_launch`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_073_reassign_cdx_notify_to_the_agent_event_hook_target`. Proof deferred to slice closeout.
- request-AC6 -> `item_073_reassign_cdx_notify_to_the_agent_event_hook_target`. Proof deferred to slice closeout.
- request-AC7 -> `item_073_reassign_cdx_notify_to_the_agent_event_hook_target`. Proof deferred to slice closeout.
- request-AC8 -> `item_073_reassign_cdx_notify_to_the_agent_event_hook_target`. Proof deferred to slice closeout.
- request-AC2 -> `item_074_provision_and_revoke_provider_hooks_in_each_session_s_home_at_launch`. Proof deferred to slice closeout.
- request-AC3 -> `item_074_provision_and_revoke_provider_hooks_in_each_session_s_home_at_launch`. Proof deferred to slice closeout.
- request-AC4 -> `item_074_provision_and_revoke_provider_hooks_in_each_session_s_home_at_launch`. Proof deferred to slice closeout.
- request-AC5 -> `item_074_provision_and_revoke_provider_hooks_in_each_session_s_home_at_launch`. Proof deferred to slice closeout.
- request-AC9 -> `item_074_provision_and_revoke_provider_hooks_in_each_session_s_home_at_launch`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# AI Context
- Summary: Orchestrate agent completion notifications
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_030_tell_the_user_which_parallel_cdx_session_finished_or_is_waiting_without_watching_terminals`
- Product brief(s): `prod_020_know_which_parallel_session_needs_you`
- Architecture decision(s): (none yet)
