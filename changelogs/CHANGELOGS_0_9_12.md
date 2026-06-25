# CDX Manager 0.9.12

## Highlights

- Prevented accidental concurrent launches that reuse the same provider profile and can invalidate shared OAuth credentials.
- Made Claude add/login prefer `claude setup-token` so new Claude sessions use the long-lived token flow by default.

## Changes

### Session launch safety

`cdx` now detects when another live session already uses the same provider profile before launching a new one.

On an interactive terminal, the CLI asks for confirmation before starting the second session. In non-interactive contexts, the launch fails with a clear message so automation does not silently create conflicting sessions.

This protects profiles that share one credentials file, where concurrent token refreshes can rotate credentials and log out the other session.

### Claude token setup

Claude add and login flows now route through `claude setup-token` by default, which produces a longer-lived token than the standard login flow.

When this setup-token flow succeeds, stale Claude credentials are removed so the newly configured token is the one used at launch. The existing `--setup-token` flag remains accepted for compatibility.

Regression coverage verifies the default Claude setup-token behavior, stale credential cleanup, and compatibility of the retained flag.

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
