# CDX Manager 0.9.9

## Highlights

- Fixed Codex session logouts caused by concurrent OAuth token refresh races.
- Refreshed the local Logics assistant bridge and canonical workflow instructions.

## Changes

### Codex token refresh stability

Codex session startup now serializes OAuth token refresh work per source session and reuses a freshly refreshed source token when multiple sessions start at the same time.

This prevents parallel launches from copying stale credentials into isolated Codex profiles while another launch is already rotating the shared token.

### Runtime observability

The provider runtime now recognizes Codex refresh-rate errors as refresh failures, making status and failure reporting more precise when token refresh is blocked or rate-limited.

Regression coverage exercises concurrent Codex launches and verifies that all isolated profiles receive the refreshed token.

### Logics workflow instructions

The local `LOGICS.md` bridge and `logics/instructions.md` were refreshed to keep release and workflow operations aligned with the current `logics-manager` commands.

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
