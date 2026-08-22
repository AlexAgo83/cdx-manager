# CDX Manager 0.20.5

## Fixes

- `cdx doctor` now uses the live Codex app-server authentication probe instead
  of trusting a local auth file, so an expired or rejected refresh token is
  reported as `login_required` with an actionable `cdx login <name>` remedy.
- `cdx auth refresh all` skips disabled Codex profiles, while an explicit
  `cdx auth refresh <name>` still lets an operator inspect a disabled profile
  deliberately.
- A bulk Codex auth refresh where every selected profile is locked now exits
  non-zero as `auth_refresh_indeterminate` instead of looking like a silent
  success without verifying any credential.
- Codex app-server diagnostics no longer keep an unread stderr pipe while
  waiting for stdout, avoiding a possible deadlock or timeout from noisy
  provider diagnostics.

## Validation

- Package smoke coverage now runs `cdx doctor --json` from both packed npm and
  wheel installs with isolated local provider shims, so packaged doctor
  regressions are caught outside the source checkout.
