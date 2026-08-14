# Maintaining the token price table

`cdx stats` reports a `USD~` estimate from `DEFAULT_TOKEN_PRICES` in
`src/run_usage.py`. Everything else in cdx's usage accounting is arithmetic
that cannot drift; these numbers change whenever a vendor decides they do, and
nothing in cdx notices on its own. This is the noticing.

## When to look

Three triggers, in descending order of usefulness:

1. **A model you use is unpriced.** `cdx stats` names it on the totals line
   (`no price for <model>`), and `scripts/check_token_prices.py --from-history`
   lists every model this machine actually ran and whether the table knows it.
   This is the real trigger: somebody started using something new.
2. **The staleness test fails.** `test_the_table_has_been_reviewed_recently_enough`
   fails once `TOKEN_PRICES_REVIEWED` is more than `TOKEN_PRICES_MAX_AGE_DAYS`
   old. It is a calendar reminder, not evidence of drift.
3. **Before cutting a release**, since the table ships with it.

## Where the numbers actually are

Two traps cost time the first time round. Both are now encoded in the script,
but the reasons live here.

**`openai.com/api/pricing` refuses automated fetches** — HTTP 403, no body. The
script therefore reads a third-party aggregator. Numbers from it carry more
doubt than the Anthropic rows, and a change should be corroborated across at
least two independent aggregators before it is written down. When they
disagree, take the majority and record the dissent in the table's comment.
On 2026-08-14 four sources said `$2.50/$15` for `gpt-5.6-terra` and one said
`$2/$12`.

**Anthropic's model table is transposed.** The docs page carries the right
numbers, but as one column per model, so a model id and its price never share a
line and the script reports those rows `unverified` rather than `ok`. Read them
by hand. This is deliberate: teaching the script the shape of one vendor's
marketing table buys a check that breaks silently at the next redesign.

An "unverified" row is not a passing row. If the script cannot confirm a price,
somebody has to look.

## What to check, beyond the numbers

The prices are the obvious part. The **ratios** are what the rest of the
accounting rests on:

- a cache read costs `0.1x` the uncached input rate,
- a cache write costs `1.25x` it,
- an output token costs `5x` on Anthropic and `6x` on OpenAI.

The cache multipliers held on both vendors when last checked, so they are
constants (`CACHE_READ_MULTIPLIER`, `CACHE_WRITE_MULTIPLIER`) rather than
per-model fields. The output ratio does *not* hold across vendors, which is why
it is derived per model from the table.

The script flags any model whose output ratio is neither 5x nor 6x. Treat that
as a signal to re-read the weighting assumptions, not just to correct a number:
a new ratio means `COST~` is now mis-ranking that model's sessions, and the
last time this surprise appeared it had been silently under-costing OpenAI
output by a fifth.

## Updating

1. `python3 scripts/check_token_prices.py` — differences, unverified rows,
   ratio surprises. Exit code 1 when something differs.
2. `python3 scripts/check_token_prices.py --from-history` — models in use that
   the table does not know.
3. Read the unverified rows by hand against the vendor's own page.
4. Edit `DEFAULT_TOKEN_PRICES` and set `TOKEN_PRICES_REVIEWED` to today, even
   when nothing changed — the date records that somebody looked, which is the
   whole point of the staleness test.
5. `npm test && npm run lint`.
6. Cut a corrective release. The table ships in the package; an edit that is
   not released changes nothing for anyone.

## What not to do

**Do not guess a price to fill a gap.** An unpriced model shows `-` and is
named on the totals line; a guessed one shows a number people act on. The
whole accounting exists because cdx used to report figures nobody could
substantiate.

**Do not price a model cdx cannot name.** The key is the model string as the
provider writes it in its own transcript (`gpt-5.6-terra`, not
`GPT-5.6 Terra`). `--from-history` prints the exact strings.

**Do not model per-request tiers.** OpenAI roughly doubles both rates above a
272K-token request. cdx records tokens per run, not per request, so it cannot
tell which requests crossed that line. Long-context work is under-costed and
that is stated in the README rather than approximated.

## Overriding without a release

Anyone can price a model locally without waiting for one:

```
CDX_TOKEN_PRICES='{"gpt-6-whatever": {"input": 3, "output": 18}}' cdx stats
```

Useful for a plan-based account whose effective rate is not the public list
price, and for pricing a new model the day it ships.
