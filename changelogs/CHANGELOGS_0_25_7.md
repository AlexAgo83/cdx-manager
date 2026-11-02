# CDX Manager 0.25.7

Release date: 2026-11-02

This patch release corrects Antigravity CLI update detection and verification.

## Fixes

- Stop comparing Antigravity CLI (`agy`) versions against the editor release feed. Report the latest CLI version as unknown and let the native `agy update` command check and apply updates after confirmation, including with `--yes`. Inventory collection remains read-only. (#89)
- Accept a successful updater's explicit `You are already on the latest version.` message on stdout or stderr when the installed version is unchanged. Otherwise require a verified version increase reaching the published version when known, and preserve updater failures. (#89)

## Maintenance

- Record tray companion checksums for v0.25.6. (`53500823f04edb69be9563d327645148439644a6`)
- Record release archive checksums for v0.25.6. (`974dfb0cac31963883456bda4beddb19b8940152`)
