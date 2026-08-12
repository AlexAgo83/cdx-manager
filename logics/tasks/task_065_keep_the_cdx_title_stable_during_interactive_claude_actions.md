## task_065_keep_the_cdx_title_stable_during_interactive_claude_actions - Keep the cdx title stable during interactive Claude actions
> From version: 0.18.6
> Schema version: 1.0
> Status: Done
> Understanding: 100%
> Confidence: 95%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# AI Context
- Summary: Delivered the Claude-only terminal-title opt-out so cdx's `session — folder` title survives a busy Claude action.
- Keywords: cdx, title, stable, during, interactive, claude, actions, CLAUDE_CODE_DISABLE_TERMINAL_TITLE, _claude_env
- Use when: Revisiting terminal-title ownership for Claude sessions or the interactive launch/resume provider environment.
- Skip when: Working on the title keeper cadence, headless or auth flows, or other providers.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Read the current Claude environment construction and launch/resume specs, confirming which paths must inherit the setting and which must remain unchanged.
- [x] 2. Add the Claude-only terminal-title opt-out at the shared environment boundary and keep cdx's title keeper unchanged.
- [x] 3. Add regression coverage for the environment value, launch/resume inheritance, and unchanged non-Claude or auth paths.
- [x] 4. Update the terminal-title documentation, run focused tests plus required validation, and record the outcome for closeout.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_107_disable_claude_s_competing_terminal_title_writes_for_cdx_sessions`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_107_disable_claude_s_competing_terminal_title_writes_for_cdx_sessions`. Proof: `_build_launch_spec` and `_build_resume_spec` call `_claude_env(..., own_terminal_title=True)` in `src/provider_runtime.py`; `test_interactive_claude_specs_disable_claude_title_writes`.
- request-AC2 -> `item_107_disable_claude_s_competing_terminal_title_writes_for_cdx_sessions`. Proof: Claude Code stops setting and clearing the title when `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1`, leaving `_TerminalTitleKeeper` as the only writer; the same test asserts the value reaches both the wrapped spec and its no-transcript fallback.
- request-AC3 -> `item_107_disable_claude_s_competing_terminal_title_writes_for_cdx_sessions`. Proof: only the env dict changed - credentials isolation, OAuth token injection, args, and transcript wrapping are untouched; `test_claude_env_ignores_an_ambient_request_to_re_enable_claude_titles` covers the forced value.
- request-AC4 -> `item_107_disable_claude_s_competing_terminal_title_writes_for_cdx_sessions`. Proof: `test_non_interactive_and_non_claude_specs_keep_claude_title_writes_untouched` asserts the variable is absent from headless, `auth login`, `setup-token`, `auth status`, and the Codex/Antigravity/Ollama launch environments.
- request-AC5 -> `item_107_disable_claude_s_competing_terminal_title_writes_for_cdx_sessions`. Proof: README "Terminal Titles" names the Claude-specific variable and its boundaries; four new tests in `test/test_runtime_py.py`.

# Validation
- 2026-08-12 `pytest -q`: 859 passed, 11 skipped, 105 subtests passed (includes the 4 new terminal-title tests).
- 2026-08-12 `npm run lint` equivalents: `node --check` on both bin scripts, `scripts/verify_project_docs.py`, `ruff check .` (all checks passed), `py_compile` over src/commands/scripts/test. Ruff and pytest ran from a scratch virtualenv because neither module is installed for the system interpreter.
- 2026-08-12 `logics-manager lint`: OK. `logics-manager audit`: OK (0 blocking issues); the AI Context and Mermaid warnings for this chain were resolved in this wave.
- Finish workflow executed on 2026-08-12.
- Linked backlog/request close verification passed.

# Report
- Added `CLAUDE_DISABLE_TERMINAL_TITLE_ENV` and an `own_terminal_title` flag to `_claude_env` in `src/provider_runtime.py`. The flag forces `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` rather than defaulting it, so an ambient `0` cannot hand the title back to Claude mid-session.
- Only `_build_launch_spec` and `_build_resume_spec` pass the flag. Headless, `auth status`, `auth login`, and `setup-token` keep their previous environment, matching the slice's out-of-scope list; the request wording that reads as "always in `_claude_env`" was resolved in favour of that boundary since headless and auth spawns own no title.
- cdx's `_TerminalTitleKeeper` and the OSC title format are unchanged.
- Documented the workaround and its limits in the README "Terminal Titles" section, and added four tests to `test/test_runtime_py.py`.
- Repo left commit-ready; no commit created.
- Finished on 2026-08-12.
- Linked backlog item(s): `item_107_disable_claude_s_competing_terminal_title_writes_for_cdx_sessions`
- Related request(s): `req_054_keep_cdx_terminal_titles_stable_while_claude_is_working`

# Links
- Request: `req_054_keep_cdx_terminal_titles_stable_while_claude_is_working`
- Product brief(s): `prod_041_stable_terminal_titles_for_cdx_managed_claude_sessions`
- Architecture decision(s): (none yet)
