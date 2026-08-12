## item_107_disable_claude_s_competing_terminal_title_writes_for_cdx_sessions - Disable Claude's competing terminal-title writes for cdx sessions
> From version: 0.18.6
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Low
> Theme: interactive-session-ergonomics
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: `_claude_env` gains an `own_terminal_title` flag that forces `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1`, and only the interactive launch and resume specs pass it.
- Keywords: disable, claude, competing, terminal, title, writes, cdx, sessions, _claude_env, provider_runtime
- Use when: Touching `_claude_env` in `src/provider_runtime.py`, the Claude launch/resume specs, or the README Terminal Titles section.
- Skip when: Changing headless, login, setup-token, or non-Claude provider environments, or the title keeper itself.

# Problem
- Claude Code updates the terminal title frequently while an action is active, overwriting cdx's lower-frequency shared title keeper.
- Increasing cdx's refresh rate would create a visible title race and needless terminal writes.
- The current environment helper does not tell Claude that cdx owns the title.

# Scope
- In:
  - Set `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` only in the cdx-generated Claude provider environment.
  - Ensure both interactive Claude launch and resume inherit the setting through the shared environment builder.
  - Add targeted tests for the environment and interactive spec paths, preserving caller environment merge semantics.
  - Update terminal-title documentation to explain that cdx disables Claude's competing title updates for cdx-managed sessions.
  - Run the focused Python runtime and launch suites, then the repository validation required by the task.
- Out:
  - Setting the variable in the user's shell or global Claude configuration.
  - Changing cdx's title keeper cadence or OSC title format.
  - Applying a guessed equivalent environment variable to Codex.
  - Changing headless, login, setup-token, or non-Claude provider environments.

# Acceptance criteria
- AC1: `_claude_env` produces `CLAUDE_CODE_DISABLE_TERMINAL_TITLE` with value `1` alongside the existing cdx-owned Claude environment settings.
- AC2: Claude launch and resume specs pass that value to the spawned provider process without changing command arguments or transcript wrapping.
- AC3: An explicit ambient value cannot cause a cdx-managed interactive Claude process to re-enable Claude title writes.
- AC4: Tests demonstrate that non-Claude provider specs and Claude auth-specific flows retain their prior contracts.
- AC5: README states that cdx disables Claude's own terminal-title updates so `session — folder` remains stable while Claude is busy.
- AC6: The focused tests and the applicable project lint/validation commands pass.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: `_claude_env` produces `CLAUDE_CODE_DISABLE_TERMINAL_TITLE` with value `1` alongside the existing cdx-owned Claude environment settings.
- request-AC2 -> This backlog slice. Proof: AC2: Claude launch and resume specs pass that value to the spawned provider process without changing command arguments or transcript wrapping.
- request-AC3 -> This backlog slice. Proof: AC3: An explicit ambient value cannot cause a cdx-managed interactive Claude process to re-enable Claude title writes.
- request-AC4 -> This backlog slice. Proof: AC4: Tests demonstrate that non-Claude provider specs and Claude auth-specific flows retain their prior contracts.
- request-AC5 -> This backlog slice. Proof: AC5: README states that cdx disables Claude's own terminal-title updates so `session — folder` remains stable while Claude is busy.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_041_stable_terminal_titles_for_cdx_managed_claude_sessions`
- Architecture decision(s): (none yet)
- Request: `req_054_keep_cdx_terminal_titles_stable_while_claude_is_working`
- Primary task(s): `task_065_keep_the_cdx_title_stable_during_interactive_claude_actions`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.

# Notes
- Task `task_065_keep_the_cdx_title_stable_during_interactive_claude_actions` was finished via `logics-manager flow finish task` on 2026-08-12.
