# CDX Manager 0.24.9

Release date: 2026-10-30

This patch tracks cache efficiency and resumes runs with pinned settings. (#69)

## Cache efficiency and run continuation

- Record per-run cache hit ratios alongside cache read, cache write, uncached input, output, and total token counts. Preserve unknown provider splits as `null`. (#69)
- Add nullable `cache_usage` summaries, input-weighted cache hit ratios, measurement coverage, and cold versus continued run comparisons to stats by session, project, and model. Show cache efficiency beside token counts in history and stats. (#69)
- Add `cdx run --continue-run RUN_ID` to resume the exact Claude or Codex conversation from a finished run with its recorded profile, model, and reasoning effort, including detached runs. Preserve parent run links and provider conversation identities. (#69)
- Refuse unavailable parents, missing transcripts, mismatched profiles, and incompatible settings. Keep continuation settings pinned by disabling automatic capacity recovery and model fallback, and rejecting `--failover` and `--isolate-workspace`. (#69)
- Attribute Codex continuation usage to exact transcript boundaries so earlier turns are not counted again. Leave per-run usage unknown when those boundaries are unavailable, and parse cache write counts when reported. (#69)

## Maintenance

- Record tray companion checksums for v0.24.8. (`2f1bb93db481ff6f06d8c61435a228ae9de9c4be`)
- Record release archive checksums for v0.24.8. (`7ff1b1cc0b11016adc5c1a30135f1553af3a53d7`)
