# CDX Manager 0.24.8

Release date: 2026-10-30

This patch improves recovery from Codex model capacity failures. (#67)

## Codex capacity recovery

- Retry headless Codex capacity failures after 1 and 2 seconds before trying configured fallback models, then ready Codex profiles in priority-aware order. Recovery also applies to detached runs and does not require `--failover`. (#67)
- Exclude disabled, logged-out, `never`, and `ask-first` profiles from automatic fallback. Limit recovery to three attempts per model and four profile switches, reporting `capacity_recovery_exhausted` when no eligible alternative remains or the budget is exhausted. (#67)
- Log recovery actions to stderr and structured run data, preserve failed attempt output, and report the effective model without changing profile settings. (#67)

## Token efficiency

- Record per-run cache hit ratios beside the existing cache read, cache write, uncached input, output, and total token fields. Preserve missing provider splits as `null` in headless, interactive, and background usage readers.
- Add nullable `cache_usage` sums, input-weighted ratios, measurement coverage, and cold versus continued comparisons to stats by session, project, and model. Display `cache 72 %` or `cache n/d` beside tokens without changing existing JSON fields.
- Add `cdx run --continue-run RUN_ID` for native Claude and Codex conversation resume with pinned model and reasoning effort, including detached runs. Persist parent links and exact conversation identities. Refuse missing, mismatched, expired, or unpinnable parents; prevent model/account fallback during a continuation.
- Measure Codex continuation usage from exact transcript boundaries so cumulative conversation totals are not billed again. Parse cache write counts when Codex reports them.
- Add provider parsing, JSON compatibility, aggregation, continuation validation, settings pinning, refusal, and parent-link regression tests.

## Maintenance

- Record tray companion checksums for v0.24.7. (`16938c0d22de4589f5b4757fd7ff55e848127e7d`)
- Record release archive checksums for v0.24.7. (`a169c3eee41fcbc97477ca4d74bfc8f77c1330d5`)
