# CDX Manager 0.26.7

Release date: 2026-11-07

## Improvements

- Expose per-profile quota provenance and freshness in status JSON (#118,
  `3a7a30b4c9b0dce099027be1a6874c2b87d574b6`). Add `quota_windows.5h` and
  `quota_windows.weekly` with the source, observation time, availability and
  unavailable reason while preserving existing fields and reset times.
- Reuse existing quota readers without additional requests. Preserve observation
  times for cached evidence and mark old or undated readings stale rather than
  inventing fresh measurements.

## Maintenance

- Record tray companion checksums for v0.26.6
  (`8e006ca40c942115cac99fd998b6f885358f17f3`).
- Record release archive checksums for v0.26.6
  (`0f0c53d2991ef84f368e73b60cb293a94ce4af4d`).
