## run_005_maintaining_the_token_price_table - Maintaining the token price table
> Status: Draft
> Category: support
> Verified: 2026-08-15, migrated from `docs/token-prices-runbook.md`.
> Related request: (none yet)
> Related backlog: (none yet)
> Related task: (none yet)
> Reminder: Update status, category, verification, and linked refs when you edit this doc.

# Trigger
- `cdx stats` reports an unpriced model.
- `scripts/check_token_prices.py` reports a difference, an unverified row, or
  a ratio surprise.
- Before a release, or when the price-review staleness test expires.

# Prerequisites
- A working checkout and access to the provider documentation.
- Do not guess a price: an unpriced model is safer than an unsupported amount.

# Procedure
1. Check the table and the models actually used:

   ```sh
   python3 scripts/check_token_prices.py
   python3 scripts/check_token_prices.py --from-history
   ```

2. Verify provider pricing. Prefer the vendor's documentation. OpenAI's price
   page can refuse automated fetches, so corroborate an alternate source with
   at least one independent source before changing a price. Anthropic's model
   table is transposed; read its model and price columns manually when the
   script reports an unverified row.

3. Update `DEFAULT_TOKEN_PRICES` in `src/run_usage.py` using the exact model
   id emitted by provider transcripts. Set `TOKEN_PRICES_REVIEWED` to today,
   even when no amount changes.

4. Check the assumptions behind the estimates: cache read is `0.1x` input,
   cache write is `1.25x`, and output is normally `5x` input for Anthropic or
   `6x` for OpenAI. Treat a different output ratio as an accounting-assumption
   review, not merely a table edit.

5. Validate and release the correction:

   ```sh
   npm test && npm run lint
   ```

# Verification
- `scripts/check_token_prices.py` has no unresolved difference.
- `--from-history` recognizes every model that should be priced.
- `cdx stats` no longer reports the addressed model as unpriced.

# Rollback
- Revert the table entry and restore the prior review date if a source was
  found to be wrong. For a temporary local amount, use
  `CDX_TOKEN_PRICES='{"model-id":{"input":3,"output":18}}' cdx stats`
  rather than publishing an unverified price.

# References
- Related request: (none yet)
- Related backlog: (none yet)
- Related task: (none yet)
- `src/run_usage.py`
- `scripts/check_token_prices.py`
