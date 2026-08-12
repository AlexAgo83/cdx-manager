## req_054_keep_cdx_terminal_titles_stable_while_claude_is_working - Keep cdx terminal titles stable while Claude is working
> From version: 0.18.6
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Complexity: Low
> Theme: interactive-session-ergonomics
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: Claude Code's animated busy title overwrites the cdx `session — folder` title, so cdx must claim title ownership for the interactive Claude sessions it starts.
- Keywords: cdx, terminal, titles, stable, while, claude, working, CLAUDE_CODE_DISABLE_TERMINAL_TITLE, provider environment
- Use when: Working on terminal-title ownership, the Claude provider environment built by cdx, or a report that a session's title changes while Claude runs an action.
- Skip when: Changing the title format or keeper cadence, Codex/Antigravity/Ollama titles, headless runs, or the operator's own shell and global Claude configuration.

# Needs
- Keep the cdx `session — folder` terminal title visible throughout an interactive Claude session, including while Claude is running an action.
- Avoid a competing high-frequency title refresh between cdx and Claude Code.
- Preserve the existing title behaviour and isolation environment for Codex, Antigravity, Ollama, headless runs, and Claude authentication flows.

# Context
- cdx owns the consistent terminal title through the shared interactive runtime, but Claude Code also writes an animated busy title during actions.
- The Claude-specific documented environment variable `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` lets cdx disable Claude's title writes while retaining Claude's in-TUI activity indicator.
- Claude launch and resume specs already derive their environment through `_claude_env`, making that provider boundary the narrow place to apply the setting.

# Acceptance criteria
- AC1: Every interactive Claude launch and resume started by cdx receives `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` in its provider environment.
- AC2: During a busy Claude action, the terminal title remains the cdx `session — folder` title rather than Claude's animated session-only title.
- AC3: The setting does not alter Claude credentials isolation, explicit caller environment handling, launch arguments, transcript capture, or notifications.
- AC4: Codex, Antigravity, Ollama, headless `cdx run`, and Claude authentication actions keep their existing environment and title behaviour.
- AC5: Runtime tests cover the Claude environment contract and the targeted launch/resume paths; documentation accurately names the Claude-specific workaround.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_041_stable_terminal_titles_for_cdx_managed_claude_sessions`
- Architecture decision(s): (none yet)

# References
- User report: a Claude action replaces the cdx `session — folder` terminal title with Claude's animated busy indicator and session name.
- src/provider_runtime.py: _TerminalTitleKeeper re-emits the shared title every five seconds, while Claude redraws its busy title much more frequently.
- Claude Code 2.1.228 installed locally: the executable contains CLAUDE_CODE_DISABLE_TERMINAL_TITLE, and its bundled changelog documents that it prevents Claude from setting and clearing the terminal title.

# Backlog
- `item_107_disable_claude_s_competing_terminal_title_writes_for_cdx_sessions`
