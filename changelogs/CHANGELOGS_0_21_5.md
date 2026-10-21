# CDX Manager 0.21.5

## Claude connectors

- A Claude profile that holds a real claude.ai login now launches with it. When the profile has a full login (`.claude/.credentials.json` with a refresh token or scopes beyond inference, or on macOS its profile-specific keychain entry), cdx no longer passes `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_PROFILE`, so running `/login` inside a session takes effect and claude.ai connectors such as Microsoft 365 load. Profiles on a setup-token are unchanged. Token values are never read for this check, only the credential's shape. The macOS keychain path is covered by unit tests only.
- `cdx status` shows each Claude profile's auth type (`setup-token` or `full-login`) in a TYPE column, in the single-session view, and as `auth_type` in `--json`. The docs explain that setup-tokens cannot load claude.ai connectors and how to switch with `/login`.
