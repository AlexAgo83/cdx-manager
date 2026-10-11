# CDX Manager 0.21.2

## Fixes

- Keep the tray companion visible to CDX on long runs: macOS purges per-user temp files untouched for about three days, which removed the companion's instance lock. CDX then saw no tray, so an update replaced the binary without stopping the old process and `cdx tray launch` could not start a new one. The companion now restores its lock within a minute when it disappears.

## Release process

- GitHub release titles are exactly their tag (`vX.Y.Z`); the checksum workflow now enforces it on publish.
