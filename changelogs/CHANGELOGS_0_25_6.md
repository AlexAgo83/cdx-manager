# CDX Manager 0.25.6

Release date: 2026-11-02

This patch release fixes provider update detection and verifies installed versions after updates.

## Fixes

- Detect advertised provider updaters and version output on both stdout and stderr. After an update, verify the installed version and report failure if it is missing, unchanged, downgraded, or still below the published version. Successful text output shows the version transition, and JSON results include before, after, and latest versions. (#87)
- Fall back to the latest stable GitHub release when Ollama's vendor API returns an empty, invalid, or failed response. Keep Linux Ollama updates manual, with an explicit maintenance reason. (#87)

## Maintenance

- Record tray companion checksums for v0.25.5. (`b64a372f9ab4abb61f1440943fca19703ad555eb`)
- Record release archive checksums for v0.25.5. (`1218145eae4201e40b8140e7a94cbcec18454e17`)
