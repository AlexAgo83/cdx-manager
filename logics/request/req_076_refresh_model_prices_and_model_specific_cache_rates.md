## req_076_refresh_model_prices_and_model_specific_cache_rates - Refresh model prices and model specific cache rates
> From version: 0.20.13
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: General
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-10-04 15:53:18

# AI Context
- Summary: Refresh stats prices for current Codex and Claude models and honor their cache read rates.
- Keywords: stats, pricing, cache, Codex, Claude
- Use when: Updating token estimates or supported model prices.
- Skip when: Changing provider authentication or model selection.

# Needs
`cdx stats` leaves 30 local Opus 5.5 runs unpriced. New GPT and Claude models
also invalidate the universal 0.1x cache-read assumption.

# Context
ADR 030 requires a chain: this changes the cost claim and weighting assumption.
Use official standard short-context USD rates reviewed on 2026-10-04.
Preserve existing model entries and unknown-model behavior. Add optional
`cache_read` prices to the existing table and environment override contract.
Do not change account model selections, publish a release, or infer unsupported
service tiers, long-context requests, one-hour TTLs, or local inference prices.

# Acceptance criteria
- AC1: GPT-6.1 Sol, GPT-6 Sol/Luna, Claude Fable/Mythos 5.1 and Opus/Sonnet 5.5 have verified prices.
- AC2: Currency estimates and weighted stats honor model-specific cache reads; legacy two-rate overrides remain supported.
- AC3: Regression tests, live history coverage and documentation record the rates, sources and estimate limits.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# References
- `src/run_usage.py`
- `test/test_usage_weighting_py.py`
- `logics/runbook/run_005_maintaining_the_token_price_table.md`

# Backlog
- `item_155_refresh_model_prices_and_model_specific_cache_rates`
