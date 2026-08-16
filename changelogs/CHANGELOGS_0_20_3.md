# CDX Manager 0.20.3

## Fixes

- Playwright, npm, pip, and uv now share one cache under `<CDX_HOME>/shared-cache`
  instead of each isolated profile re-downloading its own copy, since profile
  isolation redirects `HOME` per profile and those tools resolve their cache
  dir from it.
- A session now prints a short line when it ends, cleanly or by Ctrl-C/a
  forwarded signal: the session name, how long it ran, and this run's own
  cost (or token count when the model isn't priced). A genuine provider
  crash still gets no line.

## Performance

- `cdx status --refresh` is faster: ~2.5s → ~2.2s on a 15-profile fleet,
  verified to return identical data before and after. The Claude auth probe
  now runs concurrently across sessions instead of one at a time, and no
  longer spawns `claude auth status` twice per session (the probe and the
  usage refresh were each independently running the exact same command).
- `cdx disk profiles --candidates` is faster too: ~5.1s → ~4.6s, same
  before/after verification. Per-profile `du` calls now run concurrently
  instead of one profile at a time.
