# CDX Manager 0.20.0

## Highlights

- `cdx stats` reported token figures that were wrong by up to four orders of magnitude. Every number in that table has been rebuilt on one definition, verified against an independent reader of the same transcripts.
- Sessions are ranked by what they cost rather than by how many tokens they moved, and priced in currency where the serving model is known.
- Ollama sessions report real token usage instead of a permanent zero.
- `cdx resume` works again for Claude, and stops promising resumes that would fail.

## Changes

### One definition for token usage

Three code paths read provider usage — headless stdout, an interactive transcript, and a native background close-out — and each computed the fields its own way. They disagreed in every direction at once: one dropped cache from the total, one counted it twice, one omitted the cached field entirely. All three wrote into the same launch history and the same column, so the table mixed definitions without saying so.

`src/run_usage.py` now owns the definition and all three normalize to it. `input_tokens` is the uncached remainder on every provider; cache creation and cache read are separate fields because they cost 1.25x and 0.1x of uncached input and no summed figure can recover that split; the total covers all four token classes. The run registry normalizes on the way in, so `cdx run --json`, `cdx run-status` and `cdx run-report` publish the same shape.

An independent reader of the same transcripts now agrees with cdx exactly, field by field.

### Each run is billed for its own tokens

Both interactive readers report a cumulative figure and every run stored it, so a resumed session was re-billed for its entire history on each resume — one observed session's cache read went from 2.6M to 7.6M on a single additional launch, and `cdx stats` summed that inflation again.

A run now stores the increment over the previous run on the same transcript. A shrunk, rotated or replaced transcript reports absence rather than arithmetic, and the first run against a transcript that predates it leaves a baseline without claiming history it never measured.

### Each billed response is counted once

A Claude transcript records the same billed API response under several record ids. Counting per record inflated one real transcript by 1.55x — 2741 rows for 1765 distinct responses. De-duplication now keys on the API response itself.

### The session's own transcript

Usage was read from whichever transcript in the provider home had the newest modification time, so a run could be billed against an unrelated project's file — sessions reported three runs and eighteen output tokens. Resolution is now by the conversation id cdx already holds, and a scan that cannot conclude reports absence instead of whichever candidate it had reached.

### Ranked by cost, and priced

A raw token total ranks a cache read equal to an output token worth fifty times more, and cache reads are typically the overwhelming majority of tokens — so the old ranking was very nearly a measure of cache reads alone.

`cdx stats` gains a `COST~` column and sorts on it, weighting each token class by its cost relative to an uncached input token. A `USD~` column prices runs whose serving model cdx recorded, from a table carrying two numbers per model. A model absent from that table stays unpriced rather than charged a default tier, and the totals line names it.

`CDX_TOKEN_PRICES` overrides the table without a release. `scripts/check_token_prices.py` compares it against published pricing, a test fails once it has gone ninety days unreviewed, and `docs/token-prices-runbook.md` records where each vendor's numbers actually live.

### Ollama token usage

Ollama writes no transcript of its own, so it is now launched with `--verbose` and its per-response counts are parsed from the terminal capture cdx already takes — after the same normalization the handoff reader applies, because a real capture carries cursor sequences between individual words.

The provider-flag health check now covers flags cdx passes on its own initiative, not only permission mappings.

### Resume

`cdx <session> --resume` minted a fresh conversation id and then asked the provider to resume it, so every Claude resume failed with `No conversation found with session ID`. A resume now carries the conversation it is resuming.

Resumability is a checked fact rather than a stored string: a recorded conversation the provider never wrote degrades to `--continue` or `resume --last` and reports `conversation_not_found`, instead of being named and failing. What `cdx can-resume --json` reports and what `cdx resume` runs now read the same decision.

### Dropping figures cdx cannot vouch for

Launch history written before these definitions is fictitious rather than imprecise, and cannot be recomputed: a run's true usage is the increment its transcript gained while it ran, and nothing recorded that. `cdx repair` drops those figures and keeps the runs, so a period containing only such runs reads as absent rather than as a session that spent nothing.

## Upgrading

Usage records gain `cache_creation_tokens` and `cache_read_tokens`; existing fields keep their names and `cached_input_tokens` remains their sum. `cdx stats --json` gains `weighted_tokens`, `cost_usd`, `priced_runs` and `unpriced_models`. Nothing was removed.

`cdx can-resume --json` can now report `reason: conversation_not_found`. `resumable` stays `true` in every case that used to return it; only the strategy changes.

Run `cdx repair --dry-run` after upgrading to see how many stored records carry usage from before the fix.

## Known limits

- Historical records stay wrong until `cdx repair` drops them; recomputation is not possible.
- OpenAI's long-context tier, which roughly doubles both rates above a 272K-token request, is not modelled: cdx records tokens per run rather than per request, so long-context Codex work is under-costed.
- A run that switched models mid-way is priced at the model serving its most recent record.
- OpenAI prices were taken from third-party aggregators; `openai.com` refuses automated fetches. This is why the drift check exists.
