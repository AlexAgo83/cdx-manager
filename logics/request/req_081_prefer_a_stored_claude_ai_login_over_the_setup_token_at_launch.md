## req_081_prefer_a_stored_claude_ai_login_over_the_setup_token_at_launch - Prefer a stored claude.ai login over the setup-token at launch
> From version: 0.21.4
> Schema version: 1.0
> Status: Done
> Understanding: 90
> Confidence: 90
> Complexity: Medium
> Theme: Claude authentication
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: Claude profiles that hold a real claude.ai login must launch with it, so claude.ai connectors load after `/login`; `cdx status` shows each profile's auth type.
- Keywords: claude, login, setup-token, connectors, ANTHROPIC_PROFILE, CLAUDE_CODE_OAUTH_TOKEN, keychain, status
- Use when: Changing how the Claude launch environment chooses between a stored login and the setup-token.
- Skip when: Changing Codex authentication or the setup-token minting flow.

# Needs
- P1: At launch, if the profile holds a real claude.ai login, do not inject `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_PROFILE`, so `/login` inside a session takes effect and claude.ai connectors load.
- P1: Detect that login on Linux/Windows (`.claude/.credentials.json`) and on macOS (the profile-specific `Claude Code-credentials-<hash>` keychain entry), without reading or logging token values.
- P2: Show the auth type (`setup-token` or `full-login`) in `cdx status` and `--json`; document the connector limitation of setup-tokens and the `/login` switch.

# Priority
- Medium: connectors are silently missing in every cdx Claude session on a setup-token, with a manual workaround.

# Context
- Reproduced by the upstream maintainer: a connector enabled on claude.ai is absent from `/mcp` in a cdx session, and appears after `/login` in the same session; the next `cdx <name>` returns to the setup-token.
- Claude Code only fetches claude.ai connectors for a full login; setup-token credentials make model requests only.
- A setup-token-only profile keeps today's environment. The credential shape is checked (refresh token or scopes beyond `user:inference`), never the values.

# Acceptance criteria
- AC1: A profile with a full login in `.credentials.json` or the profile keychain entry launches without `CLAUDE_CODE_OAUTH_TOKEN` and `ANTHROPIC_PROFILE`.
- AC2: A setup-token-only profile, or one with an inference-only credential, launches as before.
- AC3: `cdx status` (table, single session, `--json`) reports `setup-token` or `full-login` for Claude profiles.
- AC4: Docs and changelog state the limitation and the switch; the macOS keychain path is unit-tested with the keychain mocked.

# Definition of Ready (DoR)
- [ ] Problem statement is explicit and user impact is clear.
- [ ] Scope boundaries (in/out) are explicit.
- [ ] Acceptance criteria are testable.
- [ ] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# References
- `src/claude_credentials.py`
- `src/provider_runtime.py`
- `test/test_claude_full_login_py.py`

# Backlog
- `item_165_prefer_a_stored_claude_ai_login_over_the_setup_token_at_launch`
