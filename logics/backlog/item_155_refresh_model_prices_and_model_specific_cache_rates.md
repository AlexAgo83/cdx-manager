## item_155_refresh_model_prices_and_model_specific_cache_rates - Refresh model prices and model specific cache rates
> From version: 0.20.13
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: High
> Theme: Operator workflow and runtime integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-10-04 15:53:19

# AI Context
- Summary: Refresh seven model prices and honor model-specific cache-read costs.
- Keywords: refresh, model, prices, specific, cache, rates
- Use when: Maintaining stats pricing and cache weighting.
- Skip when: Changing provider account models or billing tiers.

# Problem
New models are missing from stats and the universal cache-read multiplier is no longer accurate.

# Scope
- In:
  - seven verified model entries, optional cache_read rates, weighted and USD estimates, overrides, tests and docs
- Out:
  - provider selection, releases, and billing tiers not recorded per request

# Acceptance criteria
- AC1: GPT-6.1 Sol, GPT-6 Sol/Luna, Claude Fable/Mythos 5.1 and Opus/Sonnet 5.5 have verified prices.
- AC2: Currency estimates and weighted stats honor model-specific cache reads; legacy two-rate overrides remain supported.
- AC3: Regression tests, live history coverage and documentation record the rates, sources and estimate limits.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: GPT-6.1 Sol, GPT-6 Sol/Luna, Claude Fable/Mythos 5.1 and Opus/Sonnet 5.5 have verified prices.
- request-AC2 -> This backlog slice. Proof: AC2: Currency estimates and weighted stats honor model-specific cache reads; legacy two-rate overrides remain supported.
- request-AC3 -> This backlog slice. Proof: AC3: Regression tests, live history coverage and documentation record the rates, sources and estimate limits.

# Decision framing
- Product framing: Not needed
- Product signals: (none detected)
- Product follow-up: No product brief follow-up is expected based on current signals.
- Architecture framing: Not needed
- Architecture signals: (none detected)
- Architecture follow-up: No architecture decision follow-up is expected based on current signals.

# Links
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
- Request: `req_076_refresh_model_prices_and_model_specific_cache_rates`
- Primary task(s): `task_084_refresh_model_prices_and_model_specific_cache_rates`

# Priority
- Priority: Medium
- Rationale: Current local Opus 5.5 runs are unpriced; fix stats without blocking session launches.

# Notes
- Hybrid rationale: Derived from request `req_076_refresh_model_prices_and_model_specific_cache_rates` and kept bounded to one coherent delivery slice.
- Source file: `logics/request/req_076_refresh_model_prices_and_model_specific_cache_rates.md`.
- Generated locally by logics-manager.
- Task `task_084_refresh_model_prices_and_model_specific_cache_rates` was finished via `logics-manager flow finish task` on 2026-10-04.

# Tasks
- `task_084_refresh_model_prices_and_model_specific_cache_rates`
