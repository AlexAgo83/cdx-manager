# CDX Manager 0.20.14

## Current model prices in stats

- Add GPT-6.1 Sol, GPT-6 Sol, GPT-6 Luna, Claude Fable 5.1, Claude Mythos 5.1,
  Claude Opus 5.5 and Claude Sonnet 5.5 to the built-in token price table,
  reviewed against official provider documentation on 2026-10-04.
- Honor model-specific cache-read prices in both `USD~` and weighted `COST~`
  stats: 5% of input for GPT-6.1 Sol and Opus 5.5, and 2.5% for Fable/Mythos 5.1.
- `CDX_TOKEN_PRICES` accepts an optional `cache_read` price in USD per million
  tokens, including zero. Existing two-field overrides keep the 10% fallback.
- Recorded runs using these models are priced when stats are read. Unknown
  models remain unpriced; account model selections are unchanged.

## Updating the price table

- Run `cdx update` after publication to receive the new table. Updating only
  Codex or Claude does not update cdx-manager's built-in prices.
- Document the complete maintainer and installed-machine workflow in the
  pricing runbook: exact IDs, official sources, helper limitations, regression
  tests, release preparation and version/stats verification.
- Costs remain estimates at standard short-context list prices. Fast/priority,
  Batch/Flex, regional premiums, tool fees, one-hour cache writes and per-request
  long-context premiums are not modelled.

## Validation

- All 1058 Python tests pass; project lint and Logics lint pass.
- npm package contents, Python sdist/wheel build and Twine metadata checks pass.

- Regression coverage includes the seven model rates, mixed token classes,
  cache overrides, backwards compatibility and stats ranking.
- Local history recognizes all eight recorded models, including 30 Opus 5.5
  runs that were previously unpriced.
