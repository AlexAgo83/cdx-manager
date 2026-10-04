## run_005_maintaining_the_token_price_table - Maintaining the token price table
> Status: Active
> Category: support
> Verified: 2026-10-04, refreshed against official OpenAI and Claude pricing/model docs.
> Related request: req_076_refresh_model_prices_and_model_specific_cache_rates
> Related backlog: item_155_refresh_model_prices_and_model_specific_cache_rates
> Related task: task_084_refresh_model_prices_and_model_specific_cache_rates
> Reminder: Update status, category, verification, and linked refs when you edit this doc.

# Trigger
- `cdx stats` reports an unpriced model.
- `scripts/check_token_prices.py` reports a difference, an unverified row, or
  a ratio surprise.
- Before a release, or when the price-review staleness test expires.

# Prerequisites
- A working checkout and access to the provider documentation.
- Do not guess a price: an unpriced model is safer than an unsupported amount.

# Quick path for an installed CDX
The price table is bundled with **cdx-manager**, not fetched at runtime. New
Codex/Claude versions and newly available account models do not update it.
After the corrective CDX release is published, run:

```sh
cdx --version
cdx update --check
cdx update
cdx --version
cdx stats --json
```

`cdx update` uses the installation's matching update mechanism. For an explicit
published release, use `cdx update --version v0.20.14`. Do not run this command
while that version is only being prepared. `cdx update all` targets provider
and workstation tools; it is not a substitute for updating cdx-manager itself.
A source checkout is verified separately with `node bin/cdx.js --version`.

Check `CDX_TOKEN_PRICES` if an updated install still gives an unexpected amount:
it overrides built-in entries. Existing history with a recorded model is priced
again when stats are read, so no history migration or model reselection is needed.
An unknown model remains unpriced. A price entry does not grant provider access
or change `cdx model` / `cdx set` preferences.

# Maintainer procedure
1. Establish the gap without dumping transcripts or account data:

   ```sh
   git status --short
   python3 scripts/check_token_prices.py --from-history
   python3 scripts/check_token_prices.py
   ```

   The history command identifies exact emitted IDs and run counts. Also review
   current official lineups: history alone misses newly released models that
   have not been launched locally. Keep any pre-existing workspace changes.

2. Open official pricing **and model ID** pages. Start with the links in the
   latest review below. OpenAI's pricing and model pages also expose `.md`
   versions, useful when the HTML hides older rows behind “All models”. Compare
   standard short-context input, output, cached input and cache-write prices in
   USD per million tokens. Record source URLs and date. Do not infer prices for
   new aliases, local providers or account-specific names.

   The helper is a screening tool: it matches numbers near names across tiers,
   cannot independently validate cache columns, and can leave transposed Claude
   tables or dated OpenAI IDs unverified. Inspect those rows manually; report
   what remains unverified rather than treating exit code zero as full proof.

3. Edit the single table `DEFAULT_TOKEN_PRICES` in `src/run_usage.py`. Preserve
   historical entries. Add exact IDs, `input`, `output`, and an explicit
   `cache_read` when the usual 0.1x input assumption does not hold. All fields
   use USD per million tokens, not multipliers. Set `TOKEN_PRICES_REVIEWED` to
   the actual review date and record any retained historical verification limits.

   `weighted_usage` and `estimate_cost` must agree on model-specific cache
   ratios. Writes assume 1.25x input (five-minute TTL); a different write rule
   needs an accounting change, not just a new input price. Two-field environment
   overrides replace the row and retain the legacy 0.1x read fallback. An
   explicit `cache_read: 0` is valid. Unknown models must remain unpriced.

4. Add regression cases in `test/test_usage_weighting_py.py`: mixed token classes,
   weighted totals, actual stats aggregation/ranking, unknown IDs, and legacy
   versus explicit cache overrides. Update the README and this review record.
   Under ADR 030, a price-only refresh can keep evidence beside the declaration;
   a changed accounting assumption needs a Logics chain (the 0.20.14 example is
   `req_076` / `item_155` / `task_084`).

5. Validate the checkout before preparing publication:

   ```sh
   python3 -m unittest discover -s test -p 'test_usage_weighting_py.py'
   npm test
   npm run lint
   python3 scripts/check_token_prices.py --from-history
   node bin/cdx.js stats --json
   logics-manager lint --require-status
   logics-manager audit --group-by-doc
   git diff --check
   ```

   Use `rtk npm test` / `rtk npm run lint` when RTK is available. The correct
   unittest entry point is discovery; `test` is not an importable package.
   Compare unpriced model IDs and priced-run coverage, not just total dollars.

# Release and rollout
1. Run `logics-manager release status` and `logics-manager release plan <version>`.
   Align `VERSION`, `package.json`, both version fields in `package-lock.json`,
   `pyproject.toml` and the README badge. `src/cli.py` resolves its version; verify
   `node bin/cdx.js --version` instead of adding a hardcoded copy.
2. Write `changelogs/CHANGELOGS_<version_with_underscores>.md` with the model IDs,
   cache changes, estimate boundaries, update instructions and validation.
   Build/check npm and Python distributions using the release contract commands.
   Record actual results; do not mark pending publication gates passed.
3. For a preparation-only request, leave a reviewable local change and explicitly
   list pending gates. Do not fabricate checksums: GitHub archive hashes require
   the pushed tag. `npm run release:validate` reports an unrecorded development
   release separately; use `npm run release:validate -- --tag v<version>`
   once checksum metadata exists to require the target entry.
4. When publication is explicitly requested, commit/push the release, verify CI
   for that exact commit, push its version tag and generate archive metadata with
   `python3 scripts/update_release_checksums.py --tag v<version>`. Follow the
   current release workflows and contract for metadata on main and tray assets.
   The tray workflow owns the final checksum asset; do not overwrite its complete
   ledger with one missing `tray_assets`.
5. Publish using the checked-in changelog and verify GitHub assets, npm and PyPI
   for the exact version. Record evidence and run
   `logics-manager release validate <version>`. Then update installed machines
   through the quick path above and obtain fresh version/stats receipts.

# Verification
- `scripts/check_token_prices.py` has no unresolved difference.
- `--from-history` recognizes every model that should be priced.
- `cdx stats` no longer reports the addressed model as unpriced.

# Review 2026-10-04
Standard short-context USD per million tokens; cache writes assume five-minute TTL.

| Model | Input | Output | Cache read |
| --- | ---: | ---: | ---: |
| gpt-6.1-sol | 2 | 10 | 0.10 |
| gpt-6-sol | 2 | 10 | 0.20 |
| gpt-6-luna | 0.10 | 0.50 | 0.01 |
| claude-fable-5-1 | 10 | 50 | 0.25 |
| claude-mythos-5-1 | 10 | 50 | 0.25 |
| claude-opus-5-5 | 4 | 20 | 0.20 |
| claude-sonnet-5-5 | 2 | 10 | 0.20 |

Sources read: [OpenAI pricing](https://developers.openai.com/api/docs/pricing),
[GPT-6 Sol](https://developers.openai.com/api/docs/models/gpt-6-sol),
[Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing),
[Claude IDs](https://platform.claude.com/docs/en/models/overview), and
[Mythos 5.1](https://platform.claude.com/docs/en/models/mythos-5-1/overview).
Existing rates are retained. The helper reports 13 confirmed rows, zero
price differences and 21 unverified rows (Claude's transposed overview and
OpenAI dated IDs); its loose number matching does not validate cache columns.
Claude rates were checked directly on the pricing page. Historical dated
OpenAI aliases retain their prior review; the current pricing table does not
independently confirm their IDs. No unsupported aliases were added.

The local history previously had 30 unpriced Opus 5.5 launches. Provider
account model selections are unchanged. Other/local providers have no
verified generic per-token price in this table. Service tiers, regional
premiums, tools, one-hour TTLs and per-request long-context rates remain
outside these estimates; pricing is not an invoice or subscription charge.

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
