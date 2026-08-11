## req_044_alert_on_agent_turns_that_fail_before_completion - Alert on agent turns that fail before completion
> From version: 0.18.4
> Schema version: 1.0
> Status: Draft
> Understanding: 85%
> Confidence: 80%
> Complexity: Medium
> Theme: Desktop integration
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: Alert on agent turns that fail before completion
- Keywords: tray alerts, provider hooks, failed turn, rate limit, StopFailure
- Use when: Extending agent alerts to turns that end in a provider error rather than a completion.
- Skip when: Working on the completion and permission alerts already covered by req_039.

# Needs
- A turn that dies on a provider error produces no alert at all. The session goes quiet, and the user learns about it only by looking at the terminal — which is the exact situation the tray exists to avoid.
- This is the failure mode that costs the most: a rate limit or a billing error interrupts work that was expected to continue, and the longer it goes unnoticed the more idle time it produces.
- The information needed to say why is already published. Claude Code emits StopFailure with error_type — rate_limit, overloaded, authentication_failed, oauth_org_not_allowed, billing_error, invalid_request, model_not_found, server_error, max_output_tokens, unknown — and error_message.
- The tray already knows each session's remaining capacity, so a rate-limit alert can point at something the user can act on rather than only reporting a stop.

# Context
- `src/agent_notify.py` provisions `Stop` on both providers and `Notification` on Claude. Nothing subscribes to a failure event, so a failed turn is indistinguishable from a session the user simply has not looked at.
- req_039 and item_086 deliberately scope themselves to `Stop` and `PermissionRequest`. The structured envelope they introduce is what this request would carry a failure in, so this work follows them rather than competing with them.
- Codex publishes no documented equivalent of StopFailure today, so this starts as a Claude-only alert and has to degrade honestly rather than implying parity.
- error_message is provider-authored free text. It follows the same normalization, bounding, and preview-preference rules as assistant text; error_type is a closed enum and is safe metadata.
- Some error_type values are transient and some are terminal. An alert that treats an overloaded retry like a billing_error would train the user to ignore both.

# Acceptance criteria
- AC1: A Claude turn that ends in a provider error produces exactly one tray alert naming the session, the project, and the error class.
- AC2: The alert distinguishes transient failures from ones needing an action, and its wording does not imply the turn completed.
- AC3: error_message is subject to the existing preview preference, normalization, and length bound; error_type is always available as safe metadata.
- AC4: A failed turn produces no completion alert, and a completed turn produces no failure alert, including when both hooks fire for the same turn.
- AC5: The absence of a Codex equivalent is stated in user-facing documentation instead of being presented as parity.
- AC6: Focused tests cover each error class, the preview boundary, and the mutual exclusion with completion alerts; the project validation suite passes.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# References
- `src/agent_notify.py`
- `src/tray_events.py`
- `tray/src/events.rs`
- `req_039_make_cdx_tray_agent_alerts_structured_and_actionable`
- Claude Code hooks reference — https://code.claude.com/docs/en/hooks

# Backlog
- `item_091_alert_on_claude_turns_that_end_in_a_provider_error`
