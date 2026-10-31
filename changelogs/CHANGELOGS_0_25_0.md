# CDX Manager 0.25.0

Release date: 2026-10-31

This release adds per-run cost estimates and enforces estimated USD budgets. (#71)

## Run costs and budgets

- Include nullable `cost_usd` estimates in history and run results, using observed usage, the serving model, cache token rates, and the same pricing table and `CDX_TOKEN_PRICES` overrides as stats. Unknown usage or prices remain `null`. (#71)
- Add `cdx run --budget USD` to stop a run when its measured estimated spend reaches the limit. Retries, model recovery, and account failover share the run budget; a budget stop terminates the provider process tree and prevents further recovery or failover. (#71)
- Support budgets for detached and continued runs. A continuation starts a fresh budget that excludes earlier turns; detached results remain available through `cdx run-status` and `cdx run-report`. (#71)
- Report budget stops with exit code `125`, `error.code: "budget_exceeded"`, and `error.spent_usd`; include `cost_usd` and `budget_usd` in final results. Estimates depend on reported usage and known prices, so delayed updates can cause overshoot and unknown costs cannot trigger a stop. (#71)

## Maintenance

- Record tray companion checksums for v0.24.9. (`eb4de92877c91f339426b344f9f242bdede02eec`)
- Record release archive checksums for v0.24.9. (`afecbfdcf4b999663cd6937955349824728f621e`)
