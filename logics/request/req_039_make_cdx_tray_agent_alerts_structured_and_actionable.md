## req_039_make_cdx_tray_agent_alerts_structured_and_actionable - Make CDX tray agent alerts structured and actionable
> From version: 0.18.4
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 92%
> Complexity: Medium
> Theme: Desktop integration
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: Make CDX tray agent alerts structured and actionable
- Keywords: request-chain-scaffold, make cdx tray agent alerts structured and actionable, development-ready
- Use when: You need to implement or review the scaffolded workflow for Make CDX tray agent alerts structured and actionable.
- Skip when: The change is unrelated to this scaffolded request chain.

# Needs
- The active tray currently receives only a rendered title, body, and coarse kind. It cannot reliably distinguish the session, project, provider event, or safe action target without parsing display text.
- A Stop hook from Codex and Claude provides last_assistant_message, so an opted-in short completion preview is already possible; the tray should present it consistently in its notification and recent-alert history.
- Codex PermissionRequest provides the requested tool and Claude can provide the same detail, but CDX currently provisions Claude's broad Notification event instead. This loses exact metadata and can produce a delayed duplicate permission alert.
- Tray alerts must remain useful without persisting transcript paths, raw tool inputs, session identifiers, or any assistant text that the session owner did not explicitly opt into.

# Context
- src/agent_notify.py composes a sanitized title and message, including a 180-character single-line Stop preview only when CDX_NOTIFY_PREVIEW is set. It publishes below that composition boundary, so the tray currently receives the same text as the direct notifier.
- src/tray_events.py stores a versioned, bounded, append-only JSONL event with id, timestamp, kind, title, and message. tray/src/events.rs intentionally accepts forward-compatible extra fields but currently discards them.
- CDX knows the session name through its launch environment and can derive the project basename from cwd. These values should become structured event fields rather than being recovered from a localized title or message.
- The current Codex plugin provisions Stop and PermissionRequest. The current Claude configuration provisions Stop and an unfiltered Notification hook. Claude documents PermissionRequest as immediate and carrying tool_name and tool_input, while its permission_prompt Notification is delayed when the user appears away; subscribing to both for the same permission would duplicate alerts.
- Claude's Notification hook also carries the waiting states idle_prompt and agent_needs_input, which no other hook reports. The duplicate is therefore removed by filtering notification_type down to those states, not by dropping the subscription.
- Claude's PermissionRequest is a decision hook: whatever the hook writes to stdout is read as an allow or deny for the tool call. A notification hook must exit 0 with an empty stdout on every path, including failures.
- Provider transcripts are explicitly not a stable hook interface. Raw tool_input can contain commands, arguments, or secrets, so it must never be persisted or rendered. tool_name is safe metadata; an optional human-readable description must follow the same explicit preview preference, normalization, and length limit as assistant text.

# Acceptance criteria
- AC1: Each tray event has a versioned structured envelope containing kind, session, project, provider event, title, and message; optional preview, tool_name, model, and permission_reason fields are accepted only when safely available. The direct desktop notifier remains unchanged.
- AC2: A Stop event from Codex or Claude shows the existing opt-in, normalized, bounded last_assistant_message preview in the tray notification and recent-alert history. Without the existing preview opt-in, no assistant-response text is written to the tray spool.
- AC3: CDX provisions Stop and PermissionRequest for both Codex and Claude. It no longer subscribes Claude's broad Notification hook for permission delivery, so one permission request produces one tray event and one visible alert.
- AC4: A PermissionRequest tray alert identifies the session, project, and tool_name. It never persists tool_input, transcript_path, session_id, turn_id, or arbitrary provider payload. A permission reason is included only when the response-preview preference is enabled and a provider supplied a usable human-readable description.
- AC5: The tray reads structured fields without parsing title or message, displays a concise completion or attention line, and lets the user open the originating CDX session through the existing session-launch action.
- AC6: Older tray companions ignore unknown structured fields and newer companions preserve the current fallback behavior when the event payload is incomplete or malformed.
- AC7: Focused Python and Rust tests cover Codex and Claude Stop previews, exact permission routing without duplicates, privacy exclusion of raw tool input, structured event compatibility, and the tray session action; the project validation suite passes.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_028_structured_actionable_tray_agent_alerts`
- Architecture decision(s): (none yet)

# References
- src/agent_notify.py
- src/tray_events.py
- src/commands/tray.py
- tray/src/events.rs
- tray/src/menu.rs
- test/test_agent_notify_py.py
- test/test_tray_events_py.py
- logics/request/req_032_show_a_privacy_aware_preview_in_agent_completion_notifications.md
- logics/request/req_036_route_cdx_agent_alerts_through_an_active_tray_companion.md
- https://learn.chatgpt.com/docs/hooks
- https://code.claude.com/docs/en/hooks

# Backlog
- `item_086_deliver_structured_private_hook_context_to_actionable_tray_alerts`
