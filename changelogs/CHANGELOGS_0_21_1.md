# CDX Manager 0.21.1

## Fixes

- Stop the macOS tray companion from leaking memory: each poll rebuilt the menu and status icon outside any autorelease pool, so nothing was ever freed and a week-old companion reached a footprint of about 19 GB.
- Cache a failed cdx-manager release check like a successful one and lower its network timeout from 5 s to 2 s, so a degraded network no longer stalls every `cdx` command on GitHub.
