## item_076_add_opt_in_bounded_assistant_response_previews_to_agent_notifications - Add opt-in, bounded assistant-response previews to agent notifications
> From version: 0.17.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Notifications
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: Add opt-in, bounded assistant-response previews to agent notifications
- Keywords: scaffolded-backlog, add opt-in, bounded assistant-response previews to agent notifications, implementation-ready
- Use when: Implementing the scaffolded slice for Add opt-in, bounded assistant-response previews to agent notifications.
- Skip when: The change belongs to another backlog slice.

# Problem
- The completion toast only says that a turn completed, which leaves the user unable to distinguish a useful result from a request for follow-up without context switching.
- Sending raw response text by default would expose potentially sensitive content on the desktop or lock screen.
- The current generated provider configuration needs to match the current documented lifecycle event names before relying on it for richer notifications.

# Scope
- In:
  - Add one explicit per-session preview preference using the existing launch-settings parse, persistence, unset, display, and bulk-setting patterns.
  - Extract last_assistant_message only from a Stop payload, normalize it to one printable line, remove control characters, and truncate it at a small documented limit with an ellipsis when needed.
  - Keep the existing session name, repository basename, platform dispatch, opt-in notification setting, and hook failure swallowing intact.
  - Keep previews absent for attention events; use a specific attention label and safe payload metadata such as tool name when available.
  - Update generated provider hook definitions to documented supported events, without parsing transcripts or adding a new dependency.
  - Add focused unit coverage and README guidance, including the lock-screen privacy tradeoff.
- Out:
  - Reading transcript files or depending on their private format.
  - Generating a new model summary, retaining notification history, or sending text to a remote service.
  - Previews for headless execution or providers without the supported payload field.
  - Configurable preview templates, per-platform UI code, notification buttons, or notification deduplication.

# Acceptance criteria
- AC1: A session can explicitly enable and disable response previews through cdx settings, and the default remains disabled after unset or creation.
- AC2: An enabled Stop notification appends a bounded, whitespace-normalized preview from last_assistant_message, while an empty or unavailable message leaves the ordinary completion body intact.
- AC3: The preview helper removes control characters, collapses whitespace, and truncates deterministically without splitting the notification command or producing multiple lines.
- AC4: A disabled preview preference never sends last_assistant_message to send_desktop_notification.
- AC5: Attention notifications do not include last_assistant_message and identify permission attention safely when provider metadata exists.
- AC6: Generated hook configurations contain documented supported event names for each hook-capable provider and repeated provisioning leaves them unchanged.
- AC7: The notification, settings, launch, and full project test suites pass; README explains the opt-in setting and lock-screen exposure.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: A session can explicitly enable and disable response previews through cdx settings, and the default remains disabled after unset or creation.
- request-AC2 -> This backlog slice. Proof: AC2: An enabled Stop notification appends a bounded, whitespace-normalized preview from last_assistant_message, while an empty or unavailable message leaves the ordinary completion body intact.
- request-AC3 -> This backlog slice. Proof: AC3: The preview helper removes control characters, collapses whitespace, and truncates deterministically without splitting the notification command or producing multiple lines.
- request-AC4 -> This backlog slice. Proof: AC4: A disabled preview preference never sends last_assistant_message to send_desktop_notification.
- request-AC5 -> This backlog slice. Proof: AC5: Attention notifications do not include last_assistant_message and identify permission attention safely when provider metadata exists.
- request-AC6 -> This backlog slice. Proof: AC6: Generated hook configurations contain documented supported event names for each hook-capable provider and repeated provisioning leaves them unchanged.
- request-AC7 -> This backlog slice. Proof: AC7: The notification, settings, launch, and full project test suites pass; README explains the opt-in setting and lock-screen exposure.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_022_actionable_private_agent_notifications`
- Architecture decision(s): (none yet)
- Request: `req_032_show_a_privacy_aware_preview_in_agent_completion_notifications`
- Primary task(s): `task_043_orchestrate_privacy_aware_agent_notification_previews`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.

# Tasks
- `task_043_orchestrate_privacy_aware_agent_notification_previews`

# Notes
- Task `task_043_orchestrate_privacy_aware_agent_notification_previews` was finished via `logics-manager flow finish task` on 2026-08-10.
