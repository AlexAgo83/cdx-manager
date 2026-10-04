## task_084_refresh_model_prices_and_model_specific_cache_rates - Refresh model prices and model specific cache rates
> From version: 0.20.13
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Owner: codex
> Indicators reviewed: 2026-10-04 15:53:19

# AI Context
- Summary: Refresh seven model prices and honor model-specific cache-read costs.
- Keywords: refresh, model, prices, specific, cache, rates
- Use when: Maintaining stats pricing and cache weighting.
- Skip when: Changing provider account models or billing tiers.

# Definition of Done (DoD)
- [x] The backlog scope is implemented.
- [x] Acceptance criteria are covered.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# Backlog
- `item_155_refresh_model_prices_and_model_specific_cache_rates`

# Acceptance criteria
- AC1: GPT-6.1 Sol, GPT-6 Sol/Luna, Claude Fable/Mythos 5.1 and Opus/Sonnet 5.5 have verified prices.
- AC2: Currency estimates and weighted stats honor model-specific cache reads; legacy two-rate overrides remain supported.
- AC3: Regression tests, live history coverage and documentation record the rates, sources and estimate limits.

# Plan
- [x] Verify official model IDs and standard prices, including cache-read discounts.
- [x] Update the shared price table, weighted stats and environment overrides.
- [x] Cover arithmetic and stats ranking with regression tests; update README and runbook.
- [x] Validate local history coverage and close the workflow through the CLI.

# Validation
- `npm test`: 1057 tests passed before the final stats integration test was added.
- `python3 -m unittest discover -s test -p 'test_usage_weighting_py.py'`: all 23 tests passed including the final stats integration test.
- `npm run lint`: passed.
- `python3 scripts/check_token_prices.py`: zero differences, 13 confirmed, 21 unverified by the helper; manual evidence and historical alias limits are in run_005.
- `python3 scripts/check_token_prices.py --from-history`: all eight locally recorded models priced, including 30 Opus 5.5 runs.
- `node bin/cdx.js stats --json`: ok=true, 438 priced runs, no unpriced models.
- Finish workflow executed on 2026-10-04.
- Linked backlog/request close verification passed.

# Report
- Finished on 2026-10-04.
- Linked backlog item(s): `item_155_refresh_model_prices_and_model_specific_cache_rates`
- Related request(s): `req_076_refresh_model_prices_and_model_specific_cache_rates`
AC1: Added seven exact model IDs using official pricing and model references in run_005.
AC2: Optional per-million `cache_read` reaches USD and weighted costs. Tests cover
all new model rates, zero/custom cache overrides, legacy two-field overrides,
unknown models and actual stats aggregation/ranking.
AC3: Updated README and run_005 with sources, review date, manual-verification
limits and standard-tier estimate boundaries. No account settings or releases changed.
ADR 009 checkpoint: implementation, tests and affected documentation updated together.

# Links
- Request: `req_076_refresh_model_prices_and_model_specific_cache_rates`
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# AC Traceability
- request-AC1 -> This task. Proof: Official rates recorded in run_005; seven-model arithmetic, cache overrides and stats ranking verified by 23 focused tests; full suite 1057 passed, lint passed and live stats has no unpriced models. Source: `logics/tasks/task_084_refresh_model_prices_and_model_specific_cache_rates.md`
- request-AC2 -> This task. Proof: Official rates recorded in run_005; seven-model arithmetic, cache overrides and stats ranking verified by 23 focused tests; full suite 1057 passed, lint passed and live stats has no unpriced models. Source: `logics/tasks/task_084_refresh_model_prices_and_model_specific_cache_rates.md`
- request-AC3 -> This task. Proof: Official rates recorded in run_005; seven-model arithmetic, cache overrides and stats ranking verified by 23 focused tests; full suite 1057 passed, lint passed and live stats has no unpriced models. Source: `logics/tasks/task_084_refresh_model_prices_and_model_specific_cache_rates.md`
