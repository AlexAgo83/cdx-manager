# CDX Manager 0.20.1

## Fixes

- `cdx status --refresh` no longer reports a false "OAuth access token has expired" alert for a profile that is still logged in. The persisted access token's `expiresAt` is now checked offline before the quota probe runs; once it is known to be expired, the probe is skipped instead of reproducing a predictable 401 (`claude auth status` does not refresh it — only a real Claude Code invocation does). (#11)
- The stale-quota/local-auth-valid warning path now also recognizes the provider's current `OAuth access token has expired` message, not just the older `invalid authentication credentials` phrasing.
