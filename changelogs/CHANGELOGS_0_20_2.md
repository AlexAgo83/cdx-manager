# CDX Manager 0.20.2

## Fixes

- Claude transcripts up to 128 MiB are now measured. Before each relaunch, CDX
  reconciles the preceding Claude conversation when its exact transcript was
  not captured; `cdx repair --force` also repairs safely attributable history.
- Token pricing now ignores synthetic transcript model placeholders when a real
  provider model is present, so measured Claude sessions receive their price.
- `cdx history` and `cdx stats --since` now include sessions that overlap the
  requested period, including sessions that started before the window and
  completed inside it.
