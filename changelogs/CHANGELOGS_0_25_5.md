# CDX Manager 0.25.5

Release date: 2026-11-02

This patch release makes `cdx update all` report version status based on verified evidence.

## Fixes

- Compare installed tool versions with official release sources before reporting them as up to date. Report unknown status when version evidence is unavailable or inconsistent, and offer automatic updates only when a supported CLI updater or verified Homebrew installation is available. Preserve existing JSON fields and expose uncertainty with `unknown` and an optional `reason`. (#85)

## Maintenance

- Record tray companion checksums for v0.25.4. (`46ff59ba5fad3bbd7b37429371112f3f6f38a330`)
- Record release archive checksums for v0.25.4. (`8ae658e2e6f3303f575e95f58b622321cad87a60`)
