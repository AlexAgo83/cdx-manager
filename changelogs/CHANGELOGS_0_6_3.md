# Changelog (`0.6.2 -> 0.6.3`)

Release date: 2026-05-29

## Claude Authentication

- Fixed Claude Code 2.1.145 isolated auth handling by using `ANTHROPIC_CONFIG_DIR` instead of the older `CLAUDE_CONFIG_DIR` override.
- Removed leaked `CODEX_HOME` from Claude auth, launch, and status environments so Claude sessions do not write nested `.cdx` state inside isolated Claude homes.
- Stopped running a destructive Claude logout before `cdx login <name>`, preserving existing credentials when reauthenticating a session.
- Added profile email hints to Claude login so account-specific sessions open the expected Claude account in the browser.

## Claude Token Fallback

- Added automatic `claude setup-token` fallback when browser login completes but does not create isolated credentials.
- Captured the one-time setup token through a temporary transcript, wrote it to `claude-home/credentials/default.json`, and removed the temporary transcript after extraction.
- Added support for the new Anthropic `credentials/default.json` OAuth format during auth probes, launches, status refreshes, and auth bundle exports.

## Release Metadata and Documentation

- Updated package metadata, CLI version output, README badge, and pinned installer example to `v0.6.3`.

## Validation and Regression Coverage

- Added regression coverage for Claude login without pre-logout, email-hinted login, setup-token fallback, modern Anthropic credentials, and cleaned Claude environments.

## Validation and Regression Evidence

- `python3 -m unittest discover -s test -p 'test_*_py.py'`
