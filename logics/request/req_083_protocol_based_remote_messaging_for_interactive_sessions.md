## req_083_protocol_based_remote_messaging_for_interactive_sessions - Protocol-based remote messaging for interactive sessions
> From version: 0.26.14
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: High
> Theme: remote-session-control
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: cdx send drives a live interactive session through stream-json --resume (Claude) or a shared app-server (Codex), never through terminal input.
- Keywords: cdx send, stream-json, resume, app-server, --remote, control endpoint, event log
- Use when: changing how remote clients deliver messages to or read state from interactive sessions.
- Skip when: working on headless runs, quotas or the tray.

# Needs
- Let a remote chat client deliver a message to a running interactive cdx session through a supported provider protocol instead of typing into the terminal.
- Expose the session's turn state and replies from the provider protocol instead of hooks and screen scraping.
- Keep the interactive terminal usable: the operator can always take the session back from the keyboard.

# Context
- Remote clients currently paste text into a terminal multiplexer pane and infer state from the screen; prompts, busy turns, fresh sessions and interrupts each produced a distinct failure mode.
- cdx already owns the provider process: _run_interactive_provider_process in src/provider_runtime.py starts the TUI as a child and waits for it, and agent_state records hook events per session.
- Claude spike: a conversation started in the TUI was continued with `claude -p --resume <id> --input-format stream-json --output-format stream-json --verbose`; the run used subscription auth (apiKeySource none), wrote to the same transcript file (entrypoint sdk-cli), and a TUI reopened with --resume rendered every turn and kept the context.
- Codex spike: `codex app-server --listen ws://127.0.0.1:<port>` served the TUI started with `codex --remote` and a second JSON-RPC client; the client listed the loaded thread, resumed it, started a turn, received turn/started, item/* and turn/completed, and the TUI rendered the remote turn live.
- Codex refuses a Unix socket whose parent directory is writable by other users; its WebSocket transport is marked experimental.
- Claude Code fires no Stop hook on an Esc interrupt, so hook-derived state can stay 'working' after an interrupt.

# Acceptance criteria
- AC1: `cdx send <session> <text>` delivers the text to a running interactive Claude or Codex session launched with the feature enabled, without writing to its terminal input.
- AC2: For Claude, the launcher switches from the TUI to a stream-json --resume run on the same conversation when a message arrives while the TUI is idle, queues it while a TUI turn is running, and returns to the TUI with --resume on a keypress; no turn or context is lost across switches.
- AC3: For Codex, the launcher starts an app-server bound to a private endpoint and attaches the TUI with --remote; `cdx send` starts a turn on the TUI's thread as a second client and the TUI renders it live.
- AC4: Each session writes an append-only event log (JSON lines) with turn states (working, done, waiting, permission, interrupted, failed) and assistant text taken from the provider protocol; `cdx send --interrupt` interrupts the current remote turn.
- AC5: The control endpoint accepts only the session owner: a private Unix socket in a 0700 directory on Linux and macOS, and a loopback endpoint guarded by a per-session secret on Windows; no secret appears in argv, logs or the event log.
- AC6: With the feature disabled, launch, resume and headless behaviour are byte-for-byte unchanged, and existing tests pass.
- AC7: Automated tests cover the switch loop, queueing, interrupt, endpoint access control and event mapping with fake providers on Linux, macOS and Windows, plus a documented live check against the real CLIs on each platform.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_058_remote_control_of_interactive_sessions_through_provider_protocols`
- Architecture decision(s): (none yet)

# References
- Operator request 2026-11-13: a remote chat client must send and read messages without typing into the terminal
- Spike 2026-11-13: Claude TUI <-> stream-json --resume handoff; Codex app-server shared by the TUI (--remote) and a second JSON-RPC client

# Backlog
- `item_168_add_a_private_per_session_control_endpoint_and_the_cdx_send_command`
- `item_169_switch_claude_sessions_between_the_tui_and_a_stream_json_resume_run`
- `item_170_share_a_codex_app_server_between_the_tui_and_remote_clients`
- `item_171_prove_the_remote_messaging_loop_on_linux_macos_and_windows`

# Executions
| When | Runner | Run id | Title | State | PR | Notes |
| --- | --- | --- | --- | --- | --- | --- |

