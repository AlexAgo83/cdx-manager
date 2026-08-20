# CDX Manager 0.20.4

## Authentication

- Added `cdx auth refresh <name|all> [--json]`, a locked, no-generation Codex
  authentication probe. It can refresh an active provider session when the
  upstream CLI supports it, but never opens a browser, prompts for credentials,
  or fabricates a token.
- The result distinguishes `valid`, `locked`, `login_required`, and `failed`
  without exposing credential material.
- Documented manual use and an opt-in cron example. CDX never installs or
  enables a scheduler on its own.
