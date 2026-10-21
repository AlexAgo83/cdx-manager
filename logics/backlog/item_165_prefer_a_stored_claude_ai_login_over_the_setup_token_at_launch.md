## item_165_prefer_a_stored_claude_ai_login_over_the_setup_token_at_launch - Prefer a stored claude.ai login over the setup-token at launch
> From version: 0.21.4
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: High
> Theme: Operator workflow and runtime integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: Launch Claude profiles that hold a real claude.ai login without the setup-token env, and show the auth type in `cdx status`.
- Keywords: prefer, stored, claude, login, over, setup, token, launch
- Use when: Changing how the Claude launch environment picks between a stored login and the setup-token.
- Skip when: Changing Codex authentication or how setup-tokens are minted.

# Problem
P1: At launch, if the profile holds a real claude.ai login, do not inject `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_PROFILE`, so `/login` inside a session takes effect and claude.ai connectors load.
P1: Detect that login on Linux/Windows (`.claude/.credentials.json`) and on macOS (the profile-specific `Claude Code-credentials-<hash>` keychain entry), without reading or logging token values.
P2: Show the auth type (`setup-token` or `full-login`) in `cdx status` and `--json`; document the connector limitation of setup-tokens and the `/login` switch.

# Scope
- In:
  - launch env, profile login detection (file and macOS keychain), status auth type, docs, changelog
- Out:
  - minting a full login from `cdx login`, and any change to setup-token handling

# Acceptance criteria
- AC1: A profile with a full login in `.credentials.json` or the profile keychain entry launches without `CLAUDE_CODE_OAUTH_TOKEN` and `ANTHROPIC_PROFILE`.
- AC2: A setup-token-only profile, or one with an inference-only credential, launches as before.
- AC3: `cdx status` (table, single session, `--json`) reports `setup-token` or `full-login` for Claude profiles.
- AC4: Docs and changelog state the limitation and the switch; the macOS keychain path is unit-tested with the keychain mocked.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: A profile with a full login in `.credentials.json` or the profile keychain entry launches without `CLAUDE_CODE_OAUTH_TOKEN` and `ANTHROPIC_PROFILE`.
- request-AC2 -> This backlog slice. Proof: AC2: A setup-token-only profile, or one with an inference-only credential, launches as before.
- request-AC3 -> This backlog slice. Proof: AC3: `cdx status` (table, single session, `--json`) reports `setup-token` or `full-login` for Claude profiles.
- request-AC4 -> This backlog slice. Proof: AC4: Docs and changelog state the limitation and the switch; the macOS keychain path is unit-tested with the keychain mocked.

# Decision framing
- Product framing: Not needed
- Product signals: (none detected)
- Product follow-up: No product brief follow-up is expected based on current signals.
- Architecture framing: Not needed
- Architecture signals: (none detected)
- Architecture follow-up: No architecture decision follow-up is expected based on current signals.

# Links
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
- Request: `logics/request/req_081_prefer_a_stored_claude_ai_login_over_the_setup_token_at_launch.md`
- Primary task(s): (none yet)

# Priority
- Priority: Medium
- Rationale: Connectors are silently missing for every setup-token profile; a manual workaround exists.

# Notes
- Hybrid rationale: Derived from request `req_081_prefer_a_stored_claude_ai_login_over_the_setup_token_at_launch` and kept bounded to one coherent delivery slice.
- Source file: `logics/request/req_081_prefer_a_stored_claude_ai_login_over_the_setup_token_at_launch.md`.
- Generated locally by logics-manager.
- Task `task_086_prefer_a_stored_claude_ai_login_over_the_setup_token_at_launch` was finished via `logics-manager flow finish task` on 2026-10-21.

# Tasks
- `task_086_prefer_a_stored_claude_ai_login_over_the_setup_token_at_launch`
