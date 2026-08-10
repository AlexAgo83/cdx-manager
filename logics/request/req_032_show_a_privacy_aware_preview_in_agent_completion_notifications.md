## req_032_show_a_privacy_aware_preview_in_agent_completion_notifications - Show a privacy-aware preview in agent completion notifications
> From version: 0.17.0
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Notifications
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: Show a privacy-aware preview in agent completion notifications
- Keywords: request-chain-scaffold, show a privacy-aware preview in agent completion notifications, development-ready
- Use when: You need to implement or review the scaffolded workflow for Show a privacy-aware preview in agent completion notifications.
- Skip when: The change is unrelated to this scaffolded request chain.

# Needs
- A completion notification identifies the session and repository but does not tell the user what the agent concluded, so the user must still open the terminal to decide whether to return to it.
- Both hook-capable providers expose the final assistant message on their Stop payload. The notification target already receives that JSON and is the shared place to derive a safe, consistent preview.
- Assistant output can contain secrets or sensitive project information, and operating systems may show notification bodies on a lock screen. Response previews must therefore remain off until explicitly enabled per session.

# Context
- compose_notification in src/agent_notify.py currently derives only a repository basename and a coarse state from the hook event; it ignores provider payload fields beyond cwd and event name.
- The current notification setting is an explicit per-session launch preference, persisted by the existing settings flow and provisioned on the next interactive launch. A preview preference should reuse that path rather than introduce global configuration.
- The Stop payload field last_assistant_message is a supported provider interface. transcript_path is not a stable hook interface and must not be parsed to manufacture a preview.
- The generated hook configuration currently subscribes to completion and attention events. The current provider hook documentation lists Stop and PermissionRequest as supported lifecycle events; provisioning must be reconciled with the documented event names while preserving the existing safe failure behavior.
- Desktop notification backends already escape their platform-specific command input. Preview text still needs a provider-independent length limit and whitespace normalization before it reaches those backends.

# Acceptance criteria
- AC1: A session has a distinct preview preference that is off unless explicitly enabled, can be set and unset through the existing launch-settings commands, and is documented.
- AC2: When previews are enabled, a completion notification includes a single-line, bounded preview derived from last_assistant_message; missing, non-string, or empty values preserve the existing notification body without error.
- AC3: Preview text is normalized to one line, has a documented conservative character limit, and does not introduce terminal or notification-command control characters.
- AC4: When previews are disabled, no assistant-response text is passed to the desktop notification backend.
- AC5: Attention notifications remain useful without exposing an assistant-response preview; permission requests identify the attention state and, where the payload supplies it, the requested tool rather than arbitrary tool input.
- AC6: Hook provisioning uses only documented event names for each supported provider, is idempotent, and retains the existing no-failure guarantee for notification delivery and provisioning.
- AC7: Targeted unit tests cover both supported Stop payload shapes, opt-in behavior, truncation and control-character handling, absent payload fields, and provider-hook configuration; the project validation suite passes.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_022_actionable_private_agent_notifications`
- Architecture decision(s): (none yet)

# References
- src/agent_notify.py
- src/commands/launch.py
- src/cli_args.py
- src/session_service.py
- test/test_agent_notify_py.py
- README.md
- https://learn.chatgpt.com/docs/hooks
- https://code.claude.com/docs/en/hooks

# Backlog
- `item_076_add_opt_in_bounded_assistant_response_previews_to_agent_notifications`
