## task_086_prefer_a_stored_claude_ai_login_over_the_setup_token_at_launch - Prefer a stored claude.ai login over the setup-token at launch
> From version: 0.21.4
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# AI Context
- Summary: Launch Claude profiles that hold a real claude.ai login without the setup-token env, and show the auth type in `cdx status`.
- Keywords: prefer, stored, claude, login, over, setup, token, launch
- Use when: Changing how the Claude launch environment picks between a stored login and the setup-token.
- Skip when: Changing Codex authentication or how setup-tokens are minted.

# Definition of Done (DoD)
- [x] The backlog scope is implemented.
- [x] Acceptance criteria are covered.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# Backlog
- `item_165_prefer_a_stored_claude_ai_login_over_the_setup_token_at_launch`

# Acceptance criteria
- AC1: A profile with a full login in `.credentials.json` or the profile keychain entry launches without `CLAUDE_CODE_OAUTH_TOKEN` and `ANTHROPIC_PROFILE`.
- AC2: A setup-token-only profile, or one with an inference-only credential, launches as before.
- AC3: `cdx status` (table, single session, `--json`) reports `setup-token` or `full-login` for Claude profiles.
- AC4: Docs and changelog state the limitation and the switch; the macOS keychain path is unit-tested with the keychain mocked.

# Plan
- [ ] Use `python3 -m logics_manager flow progress task task_086_prefer_a_stored_claude_ai_login_over_the_setup_token_at_launch.md --progress <n>%` during multi-wave work.
- [ ] Run `python3 -m logics_manager flow finish task task_086_prefer_a_stored_claude_ai_login_over_the_setup_token_at_launch.md` after implementation.

# Validation
- `npm test`, `ruff check` on changed files, `npm run lint`, `cargo test --manifest-path tray/Cargo.toml`. macOS keychain path is unit-tested with the keychain mocked; not run on a Mac.
- Finish workflow executed on 2026-10-21.
- Linked backlog/request close verification passed.

# Report
- Detection in `src/claude_credentials.py` (`has_full_claude_login`, `claude_auth_type`); launch env in `_claude_env` and `_read_claude_launch_oauth_token`; TYPE column and `auth_type`. Tests in `test/test_claude_full_login_py.py`.
- Finished on 2026-10-21.
- Linked backlog item(s): `item_165_prefer_a_stored_claude_ai_login_over_the_setup_token_at_launch`
- Related request(s): `req_081_prefer_a_stored_claude_ai_login_over_the_setup_token_at_launch`

# Links
- Request: `req_081_prefer_a_stored_claude_ai_login_over_the_setup_token_at_launch`
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
