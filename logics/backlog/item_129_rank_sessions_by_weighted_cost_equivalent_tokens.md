## item_129_rank_sessions_by_weighted_cost_equivalent_tokens - Rank sessions by weighted cost-equivalent tokens
> From version: 0.19.3
> Schema version: 1.0
> Status: In progress
> Understanding: 85
> Confidence: 80
> Progress: 40%
> Complexity: Medium
> Theme: Usage accounting
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-14 10:26:31

# AI Context
- Summary: A raw token sum ranks a cache read equal to an output token that costs fifty times more; this slice weights the four token classes by their published price ratios, which are identical across every current model and so need no price table.
- Keywords: weighted tokens, cost-equivalent, cache_read, cache_creation, price ratios, stats ranking
- Use when: Changing how `cdx stats` ranks or totals token spend.
- Skip when: Changing how tokens are read or stored — those are `item_126`, `item_127`, and `item_128`.

# Problem
- Even once the arithmetic is correct, a raw token total is a misleading measure of what a session cost. The four token classes are not interchangeable: relative to uncached input, a cache read is worth 0.1x, a cache write 1.25x, and an output token 5x. A raw sum ranks a cache read equal to an output token that costs fifty times more.
- The distortion is not marginal here. An independent read of one machine's transcripts showed cache reads at roughly 99% of all tokens consumed. A raw total is therefore, in practice, a measure of cache reads and almost nothing else, and the session that spent the most on output can sort below one that mostly replayed a cache.
- The ratios are stable in a way absolute prices are not: across the current model lineup, output is 5x input on every model, and the cache multipliers do not vary by model either. Only the absolute price per million tokens changes between tiers. A weighting therefore needs no per-model table and cannot go stale the way a price list would.
- The weighting cannot be applied until `cached_input_tokens` is split, because cache creation and cache read differ by a factor of 12.5 and are currently summed into one field. That split is `item_126`'s work; this slice depends on it.

# Scope
- In:
  - Define the weights once, as ratios relative to uncached input, with the rationale recorded next to them: cache read 0.1x, cache write 1.25x, output 5x. State in the code that these are ratios and not prices, and why that distinction is what keeps the table absent.
  - Compute a weighted cost-equivalent figure per session from the normalized usage record.
  - Rank the stats table by that figure rather than by the raw total, so the session that cost the most appears first.
  - Surface the weighted figure in the table, keeping the four raw counts visible — the raw numbers are facts and stay; the weighted figure is the comparison.
  - Handle the cache-write TTL difference honestly: the 1.25x multiplier is the five-minute TTL, and a one-hour TTL is 2x. Either detect the TTL, or document which one the weighting assumes and why the error is acceptable.
  - Document the weighting in the README alongside the stats columns, including the fact that it is provider-relative and not a currency amount.
  - Add a test asserting that a session dominated by cache reads ranks below a session with comparable raw totals but substantial output.
- Out:
  - No currency conversion or per-model price table — that is `item_130`.
  - No change to how usage is read, stored, or normalized.
  - No new provider integrations, and no attempt to weight Codex usage against Claude usage until the underlying field semantics agree.

# Acceptance criteria
- Given a session whose tokens are overwhelmingly cache reads and one with fewer tokens but substantial output, the second ranks above the first.
- Given two sessions with identical raw totals but different splits across input, cache read, cache write, and output, their weighted figures differ and the ordering follows the weighting.
- Given the stats table, the ranking key is the weighted figure and the four raw counts remain visible and unmodified.
- The weights are defined in exactly one place, expressed as ratios relative to uncached input, with their rationale recorded beside them.
- The cache-write TTL assumption is either detected or stated explicitly, rather than left implicit in a single multiplier.
- The README explains what the weighted column means and states that it is a provider-relative figure, not a cost in currency.

# AC Traceability
- request-AC11 -> This backlog slice. Proof: Given a session whose tokens are overwhelmingly cache reads and one with fewer tokens but substantial output, the second ranks above the first.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_049_token_numbers_a_user_can_act_on`
- Architecture decision(s): (none yet)
- Request: `req_063_make_cdx_stats_report_the_tokens_a_session_actually_spent`
- Primary task(s): `task_073_orchestrate_truthful_token_accounting_for_cdx_stats`

# Priority
- Priority: Medium
- Rationale: Depends on the corrected arithmetic and the split cache field; it is what makes the corrected numbers actionable rather than merely accurate.
