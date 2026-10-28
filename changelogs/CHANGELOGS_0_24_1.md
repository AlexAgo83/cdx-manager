# CDX Manager 0.24.1

This patch makes resumed sessions report their state like launched ones.

## Sessions

- `cdx resume <name>` (and `cdx <name> --resume`) now gives the provider the same agent and notify environment as a launch: a resumed Claude session sets `CDX_SESSION_NAME` for its hooks and appears in `cdx agents`, and it also gets the shared tool cache and scrub-env settings.
