# CDX Manager 0.9.10

## Highlights

- Clarified Claude status warnings when quota refresh fails but local Claude auth is still valid.

## Changes

### Claude status diagnostics

`cdx status` now distinguishes a Claude quota refresh failure from a local Claude login failure.

When Anthropic quota probing returns an invalid-credentials response while `claude auth status` still reports an authenticated session, the JSON warning keeps the existing `claude_refresh_failed` code for compatibility and adds:

- `auth_status: authenticated`
- `status_freshness: stale`
- a message explaining that cached quota values may be stale

The text-mode warning now says that local auth is still valid instead of implying that the Claude account itself is down.

Regression coverage verifies both the JSON payload and terminal warning for this mixed auth/quota-refresh state.

## Validation

- `npm run release:validate`
- `npm run lint`
- `npm test`
- `logics-manager lint --require-status`
- `logics-manager audit`
- `git diff --check`
- `npm --cache /private/tmp/cdx-npm-cache pack --dry-run`
- `python -m build`
- `python -m twine check dist/*`
