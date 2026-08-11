## item_086_deliver_structured_private_hook_context_to_actionable_tray_alerts - Deliver structured, private hook context to actionable tray alerts
> From version: 0.18.4
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Desktop integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: Deliver structured, private hook context to actionable tray alerts
- Keywords: scaffolded-backlog, deliver structured, private hook context to actionable tray alerts, implementation-ready
- Use when: Implementing the scaffolded slice for Deliver structured, private hook context to actionable tray alerts.
- Skip when: The change belongs to another backlog slice.

# Problem
- Rendered notification text is a presentation boundary, not a reliable transport contract for a tray that needs an action target and event-specific display.
- Claude's broad delayed Notification hook cannot provide the same immediate, exact permission context as Codex PermissionRequest without risking duplicate alerts.

# Scope
- In:
  - Extend the existing tray event schema and Rust event parser with a compact forward-compatible structured envelope.
  - Derive session and project from CDX-owned context; map only documented safe Stop and PermissionRequest fields from each provider.
  - Provision Stop and PermissionRequest for both providers, replacing Claude's unfiltered Notification subscription for agent-alert delivery.
  - Render structured completion and permission items in the existing tray notification and bounded history, with an action that reuses the existing session-launch path.
  - Apply the existing response-preview opt-in, normalization, and bound to all assistant text and optional permission descriptions.
  - Add focused Python and Rust coverage plus concise user-facing documentation.
- Out:
  - Changing the existing direct OS notification copy or its fallback ownership semantics.
  - Parsing, storing, or displaying transcript contents, tool_input, raw command lines, MCP arguments, or provider identifiers.
  - Support for every provider lifecycle event, background notification archives, toast buttons, or arbitrary command execution from alert history.
  - Changing tray installation, heartbeat, spool ownership, WSL transport, or notification permissions.

# Acceptance criteria
- AC1: The tray event schema carries structured session, project, provider event, safe optional preview, tool name, model, and permission reason data without making older readers fail.
- AC2: Completion and permission wording comes from structured event fields and never from parsing a title or body string.
- AC3: Codex and Claude Stop and PermissionRequest hooks produce one equivalent sanitized alert per event; Claude's former broad Notification route cannot add a delayed duplicate.
- AC4: Raw tool input and transcript paths are absent from persisted and rendered data; assistant and reason text require the existing explicit preview preference.
- AC5: Selecting a recent alert opens the matching session through the current tray session action path, while a malformed or old event remains harmless.
- AC6: Focused tests and the project validation suite pass.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: The tray event schema carries structured session, project, provider event, safe optional preview, tool name, model, and permission reason data without making older readers fail.
- request-AC2 -> This backlog slice. Proof: AC2: Completion and permission wording comes from structured event fields and never from parsing a title or body string.
- request-AC3 -> This backlog slice. Proof: AC3: Codex and Claude Stop and PermissionRequest hooks produce one equivalent sanitized alert per event; Claude's former broad Notification route cannot add a delayed duplicate.
- request-AC4 -> This backlog slice. Proof: AC4: Raw tool input and transcript paths are absent from persisted and rendered data; assistant and reason text require the existing explicit preview preference.
- request-AC5 -> This backlog slice. Proof: AC5: Selecting a recent alert opens the matching session through the current tray session action path, while a malformed or old event remains harmless.
- request-AC6 -> This backlog slice. Proof: AC6: Focused tests and the project validation suite pass.
- request-AC7 -> This backlog slice. Proof: AC6: Focused tests and the project validation suite pass.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_028_structured_actionable_tray_agent_alerts`
- Architecture decision(s): (none yet)
- Request: `req_039_make_cdx_tray_agent_alerts_structured_and_actionable`
- Primary task(s): `task_050_orchestrate_structured_actionable_cdx_tray_alerts`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
