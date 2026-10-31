# CDX Manager 0.25.1

Release date: 2026-10-31

This patch release preserves shared Playwright browsers in isolated workspaces. (#73)

## Fixes

- Force `PLAYWRIGHT_SKIP_BROWSER_GC=1` in isolated preparation and provider environments so Playwright does not delete shared browser revisions whose package references are only visible on the host. Browser installation remains available; cache cleanup remains an explicit operator operation. (#73)

## Maintenance

- Record tray companion checksums for v0.25.0. (`c766e752cbf79c74bcc2a80ab39dc5f7364d7fd7`)
- Record release archive checksums for v0.25.0. (`feb0fbc276b0456d238cf64fada6aa34a96890fa`)
