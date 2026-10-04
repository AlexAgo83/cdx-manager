## req_078_review_findings_stats_attribution_and_pricing_input_validation - Review findings: stats attribution and pricing input validation
> From version: 0.20.14
> Schema version: 1.0
> Status: Obsolete
> Understanding: 95
> Confidence: 95
> Complexity: Medium
> Theme: Usage accounting
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: Stats accounting has reproduced gaps in failover attribution, interactive run boundaries, and custom price validation; core normalization and sequential-resume tests pass.
- Keywords: stats, usage, failover, baseline, pricing, audit
- Use when: Assessing correctness of per-session token totals and estimated costs.
- Skip when: Changing live quota percentages or provider authentication.

# Needs
- P2: Attribute each failover attempt's measured tokens and duration to the session that consumed them, without losing earlier attempts.
- P2: Measure interactive consumption against the actual run start, or explicitly report uncertainty when no trustworthy baseline exists.
- P2: Validate custom rates and handle zero-input pricing without arithmetic failures or negative costs.
- Capture only: no implementation or delivery chain is committed by this review.

# Priority
- Medium: these defects affect the accuracy and availability of reporting; reproductions did not modify original usage data or spend real provider credits.

# Context
- Reviewed revision: `47d36cc`, version 0.20.14, on 2026-10-04. Earlier audit req_077 and its index changes were already present and preserved.
- Traced launch-history persistence, interactive transcript readers, normalization, headless execution/failover, stats aggregation/rendering, period filtering, and custom pricing.
- Compared the current implementation with completed req_063, req_065, and the model-pricing work in req_076. Findings concern remaining boundaries, not the already-fixed cumulative double counting or cache-inclusive input arithmetic.
- Scope is code and synthetic-data verification. No real provider execution or private transcript inspection; published prices were not independently revalidated in this review.

## Finding 1 — Failover reports the last attempt under the first session (P2)
- Evidence: `src/commands/runs.py:648-649` overwrites run_info on every attempt. The final success/failure history writes at lines 717 and 757 use the original session name, even though the final provider call uses run_session.
- Reproduction: execute the real CLI command dispatcher with the existing synthetic provider harness. Session work1 emits 100 input and 10 output tokens then an exhaustion error; work2 emits 200 input and 20 output tokens and succeeds.
- Observed: the command's final session is work2; history contains only one record, named work1, with 200 input and 20 output tokens. Stats repeats that attribution; work1's own 100/10 tokens are missing. Expected measured consumption across both attempts is 300 input and 30 output.
- Impact: both account attribution and total consumption are incorrect after failover. Earlier attempt durations are likewise not accumulated by this loop.
- Coverage gap: `test/test_commands_runs_py.py:1490` checks final session and registry occupancies but not history/statistics for usage-bearing attempts.
- Candidate correction: retain attempt-level accounting associated with the session that ran each attempt while preserving the single logical run identity.

## Finding 2 — A previous run's ending snapshot is not this run's starting snapshot (P2)
- Evidence: `src/commands/launch.py:372-394` subtracts the most recent stored cumulative for a matching transcript, not a snapshot taken when the new launch begins. `src/commands/launch.py:293` performs the read after provider execution.
- Reproduction: a first managed run records 10 output tokens. The same transcript gains 50 tokens outside that managed run; a later managed run starts and adds 20 tokens. Calling the existing attachment helper against real temporary JSONL records records 70 output tokens for the second run, not 20.
- Impact: activity outside the managed interval is attributed to the next run and its reporting period. This is distinct from the fixed sequential-resume case, which assumes no intervening transcript changes.
- Related limit: the caller supplies only 50 history entries (lines 273 and 293). A baseline outside that window is unavailable even when retained on disk; an old resumed transcript then records no measured usage for that launch.
- Candidate correction: capture a trustworthy starting baseline when the transcript can be identified, and keep uncertain attribution visible when it cannot. Overlapping writers need an explicit supported behavior, not a claim that two endpoint snapshots establish ownership.

## Finding 3 — Custom rates can crash stats or create negative costs (P2)
- Evidence: `src/run_usage.py:223-237` catches invalid JSON but does not validate rate conversions, signs, or finiteness. `output_multiplier` and `cache_read_multiplier` at lines 107-120 divide by input price.
- Reproduction: aggregate a normalized record with 100 input and 10 output tokens for model custom while setting CDX_TOKEN_PRICES to a row with output=2 and the following input values.
  - input=0: ZeroDivisionError.
  - input="invalid": ValueError during float conversion.
  - input=-1: cost_usd=-0.00008, accepted as a priced run.
- Impact: a syntactically valid documented override can make reporting fail or publish nonsensical negative costs. A free-input tariff is also not representable by the current ratio calculation.
- Candidate correction: validate finite nonnegative currency rates, reject invalid entries with actionable diagnostics, and explicitly handle an undefined relative weight when input price is zero. Do not invent a paid price for a free tier.

## Additional observations and explicit limits
- Core strengths: normalized uncached input; distinct cache creation/read; reasoning excluded from the additive total; response identity deduplication; sequential cumulative deltas; unvouched legacy data excluded; unknown models remain unpriced.
- Maintainability: `src/commands/status.py:336-389` repeats the entire row-finalization loop twice. It is redundant in the observed valid cases; remove the second copy when touching this area rather than introducing another abstraction.
- Headless cost coverage: the synthetic run explicitly selected a known model, but history had no usage_model and priced_runs was zero. The headless path extracts usage but never attaches the observed serving model. This is visible missing price coverage, not evidence that configured and actually served models should be assumed identical. Consider recording provider-reported models when available.
- Period semantics: `src/cli_args.py:765-784` includes an entire run in every period it overlaps. Adjacent daily totals are therefore not additive for a run crossing midnight. This is an intentional policy in code, not an arithmetic defect, but callers need to understand that these are totals for overlapping runs rather than tokens timestamped inside the interval.
- COST~ uses model-relative weights and is not a common currency across models/providers. Sorting on it does not establish a ranking by dollar spend. README documents this limitation.
- USD~ is an estimate at the currently loaded list-price table; README documents last-model attribution for mixed-model runs, omitted service-tier/tool/long-context adjustments, and recalculation of old runs after table updates. Treat it as an estimate, not an invoice or immutable historical billing ledger.
- Running interactive work is recorded on completion; these statistics are not a live token meter.

## Validation observed
- `rtk proxy node bin/python-runner.js -m pytest -q test/test_commands_status_py.py test/test_commands_runs_py.py test/test_interactive_usage_py.py test/test_usage_delta_py.py test/test_usage_weighting_py.py test/test_unvouched_usage_py.py test/test_usage_backfill_py.py`: 181 passed in 1.78 seconds.
- Failover reproduction used the real main dispatcher and existing synthetic process fixtures, followed by history and stats aggregation.
- Run-boundary reproduction used temporary transcript records and the existing interactive attachment helper.
- Price reproductions used temporary environment overrides and the actual aggregation function.
- No application code or tracked tests were changed.

# Acceptance criteria
- AC1: A usage-bearing two-attempt failover preserves both attempts' totals and correct session attribution in stats while retaining one logical run identity.
- AC2: A resumed run does not claim tokens added before its start; missing or ambiguous baselines have explicit behavior covered by regressions.
- AC3: Invalid, negative, nonfinite, and zero-input custom rates are handled deliberately; no uncaught numeric conversion/division error or negative estimated cost is emitted.
- AC4: Existing usage/CLI regression suites remain green, and user-facing period/cost semantics remain consistent with the implementation.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# References
- `src/commands/status.py`
- `src/commands/launch.py`
- `src/commands/runs.py`
- `src/run_usage.py`
- `src/interactive_usage.py`
- `README.md`

# Backlog
- none

# Links
- Superseded by: `req_080_harden_reviewed_data_integrity_stats_accounting_and_handoff_recovery`
