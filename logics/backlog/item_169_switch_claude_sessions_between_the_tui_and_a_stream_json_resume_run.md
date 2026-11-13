## item_169_switch_claude_sessions_between_the_tui_and_a_stream_json_resume_run - Switch Claude sessions between the TUI and a stream-json resume run
> From version: 0.26.14
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: High
> Theme: remote-session-control
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: switch, claude, sessions, between, tui, stream, json, resume, run
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- Claude Code has no attach mode: a second writer must continue the conversation with --resume while the TUI is closed.

# Scope
- In:
  - A local/remote loop around the interactive Claude child: idle detection from the session's own hook state, graceful TUI exit, a stream-json --resume run fed from the endpoint, and a keypress return to the TUI with --resume.
  - Queueing of messages received while a TUI turn is running.
  - Event mapping from stream-json (system, assistant, result, error) to the event log, and interrupt of the remote run.
- Out:
  - Permission prompts inside remote runs beyond the session's configured permission mode.

# Acceptance criteria
- AC2: A conversation keeps its context across TUI -> remote -> TUI, on the same conversation id.
- AC4: The event log records working, done, interrupted and failed states and the assistant text of remote turns.

# AC Traceability
- request-AC2 -> This backlog slice. Proof: AC2: A conversation keeps its context across TUI -> remote -> TUI, on the same conversation id.
- request-AC4 -> This backlog slice. Proof: AC4: The event log records working, done, interrupted and failed states and the assistant text of remote turns.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_058_remote_control_of_interactive_sessions_through_provider_protocols`
- Architecture decision(s): (none yet)
- Request: `req_083_protocol_based_remote_messaging_for_interactive_sessions`
- Primary task(s): `task_088_implement_protocol_based_remote_messaging_for_interactive_sessions`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.

# Executions
| When | Runner | Run id | Title | State | PR | Notes |
| --- | --- | --- | --- | --- | --- | --- |

