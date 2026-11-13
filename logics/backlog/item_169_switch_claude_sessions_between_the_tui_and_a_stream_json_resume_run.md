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
  - The same loop for Antigravity through a small per-provider adapter (src/remote_antigravity.py): see "Antigravity" below.
- Out:
  - Permission prompts inside remote runs beyond the session's configured permission mode.

# Acceptance criteria
- AC2: A conversation keeps its context across TUI -> remote -> TUI, on the same conversation id.
- AC4: The event log records working, done, interrupted and failed states and the assistant text of remote turns.

# AC Traceability
- request-AC2 -> This backlog slice. Proof: AC2: A conversation keeps its context across TUI -> remote -> TUI, on the same conversation id.
- request-AC4 -> This backlog slice. Proof: AC4: The event log records working, done, interrupted and failed states and the assistant text of remote turns.

# Antigravity
- The switch loop in src/remote_claude.py is provider-agnostic: an adapter supplies TUI idleness, the piloted argv, stream event mapping, the user message shape and the interrupt. ClaudeAdapter keeps the Claude behaviour; AntigravityAdapter adds agy.
- Piloted mode (agy 1.5.8): `agy [launch args] [--conversation <id>] --input-format stream-json --output-format stream-json -p=`. `-p` takes a value, so it is passed as `-p=` last. Input is one `{"event":"user","message":{"role":"user","content":...}}` line per turn; one process runs several turns and ends on stdin EOF.
- Output: `init` (carries conversation_id), `step_update` with `text_delta` chunks per `agent_response` step (the reply is whole when its step is DONE), and `result` with status SUCCESS, or ERROR with `finished_reason` (interrupted on SIGINT).
- Conversation id: cdx cannot fix it at TUI launch, so the adapter reads agy's own index, `~/.gemini/antigravity-cli/conversation_summaries.db` in the profile home: the newest conversation whose workspace is the launch directory, modified since the launch. A TUI that never started a conversation gets its id from the piloted run's `init` event. The TUI comes back with `agy --conversation <id>`.
- TUI idleness: the same index row (`status` CASCADE_RUN_STATUS_IDLE and `not_fully_idle` false); an unreadable index counts as busy, a missing row as idle.
- Interrupt: agy ignores every stream input event except `user`, so `cdx send --interrupt` sends SIGINT (terminate on Windows). agy reports the turn as interrupted and exits; the session stays remote and the next message starts a new run on the same conversation.
- Only `launch` is taken over: cdx has no Antigravity resume. Limit: two agy TUIs of one profile in the same directory at once are told apart only by recency.
- Live check 2026-11-13 on Linux (an existing Antigravity profile): see task_088 Report.

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

