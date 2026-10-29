# CDX Manager 0.24.3

Release date: 2026-10-29

This patch preserves observed serving models in run history and reports for more reliable usage attribution and pricing. (#57)

## Runs and statistics

- Expose `usage_model` separately from the requested `model` in completed run JSON and registry reports, and retain observed model evidence in interactive history even when token usage is unavailable.
- Recover Codex model evidence from the exact rollout identified by `thread.started.thread_id`, while keeping token totals from the run's own output. Configured defaults alone do not establish the serving model; missing or mixed model evidence stays unpriced.
- Group Claude's `[1m]` context variants with their base model in `cdx stats --by model`, preserving the original model string and per-run pricing.

These changes apply to newly recorded runs; existing history is not rewritten.
