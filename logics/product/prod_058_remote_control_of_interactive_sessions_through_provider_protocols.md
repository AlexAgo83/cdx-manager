## prod_058_remote_control_of_interactive_sessions_through_provider_protocols - Remote control of interactive sessions through provider protocols
> Date: 2026-11-13
> Status: Proposed
> Related request: `req_083_protocol_based_remote_messaging_for_interactive_sessions`
> Related backlog: `item_168_add_a_private_per_session_control_endpoint_and_the_cdx_send_command`, `item_169_switch_claude_sessions_between_the_tui_and_a_stream_json_resume_run`, `item_170_share_a_codex_app_server_between_the_tui_and_remote_clients`, `item_171_prove_the_remote_messaging_loop_on_linux_macos_and_windows`
> Related task: `task_088_implement_protocol_based_remote_messaging_for_interactive_sessions`
> Related architecture: (none yet)
> Reminder: Update status, linked refs, scope, decisions, success signals, and open questions when you edit this doc.

# Overview
cdx lets a remote chat client drive the same interactive session the operator sees in the terminal, using the providers' own programmatic interfaces.

# Goals
- Reliable message delivery and state for remote clients, with no terminal typing or screen parsing.
- One conversation shared between the terminal and the remote client, with the keyboard always able to take it back.
- Identical behaviour on Linux, macOS and Windows.

# Non-goals
- Building the remote client user interface.
- Supporting providers other than Claude and Codex in this delivery.
- Exposing the control endpoint beyond the local machine.

# Scope and guardrails
- In: scaffolded request, product, backlog, orchestration task, validation, and handoff context.
- Out: unrelated workflow docs and implementation of generated tasks.

# Key product decisions
- Use structured input as the source of truth for generated docs.
- Keep generated write paths local and repo-bounded.

# Success signals
- Generated docs pass lint and audit without broad manual rewrites.
- Context-pack output can be handed to an implementation agent directly.

# References
- Product back-reference: `req_083_protocol_based_remote_messaging_for_interactive_sessions`
- Task back-reference: `task_088_implement_protocol_based_remote_messaging_for_interactive_sessions`
