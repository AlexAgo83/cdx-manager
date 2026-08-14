## task_073_orchestrate_truthful_token_accounting_for_cdx_stats - Orchestrate truthful token accounting for cdx stats
> From version: 0.19.3
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 90%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-14 12:13:18
> Owner: claude

# AI Context
- Summary: Sequences the three slices so definitions land before arithmetic, arithmetic before per-run deltas, and transcript resolution last, keeping each behavior change attributable to one step.
- Keywords: token accounting, cdx stats, usage readers, per-run delta, transcript resolution, coverage measurement
- Use when: Implementing or sequencing any part of `req_063`.
- Skip when: Working on provider rate limits, credits, or quota display.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Inventory every producer and consumer of a usage record before changing any of them. Producers: `run_usage`, `interactive_usage`, `provider_background`. Consumers: the stats table, the run registry, and the `cdx run` / `run-status` / `run-report` JSON payloads. The third producer was missed on the first pass of this request; assume the inventory is the deliverable, not a formality.
- [x] 2. Capture the current behavior as fixtures: a real Claude transcript with cache-heavy records, a Codex rollout with several `token_count` events, a native background close-out, and a growing-transcript pair simulating a resume. Record what each of today's three readers returns, so every later change has a baseline rather than an intention.
- [x] 3. Settle the field definitions before touching any reader — whether IN and TOTAL include cached input — and write the decision down in code and README. All three readers and both providers then normalize to that one definition; do not let the table reconcile a difference the readers should have resolved.
- [x] 4. Fix the arithmetic: Claude's total to cover cached input, the within-record cache double count in `run_usage._usage_from_dict`, and `provider_background`'s missing cache fields and inverted total. Split cache creation from cache reads while you are in all three readers — they cost 1.25x and 0.1x, and the weighting later has no way to separate them after the fact. Confirm the stats sort key is the same number the TOTAL column prints.
- [x] 5. Normalize at the run registry boundary so the JSON surfaces publish the shared shape, then reconcile the README's token claims — the column meanings, the "never counted twice" invariant at `README.md:711`, and the headless-only description at `README.md:540` — against what the code now does.
- [x] 6. Then fix what a run stores. The delta work depends on the definitions being settled, and it is the change that actually stops the numbers inflating on resume. Use the already-recorded `provider_transcript_path` as the anchor, establish an equivalent anchor for the background path which has none, and decide explicitly what a first run against a pre-existing transcript records.
- [x] 7. Handle the degenerate transcript cases — shrunk, rotated, replaced — as absence rather than as arithmetic. A missing number is recoverable; a wrong one is not.
- [x] 8. Replace the mtime guess with conversation-id resolution last, so the delta tests are already green and any coverage change is attributable to this step alone. Reuse `find_session_transcript` (`src/provider_background.py:193`), which already does this for the background path — the outcome is one resolver, not a better second one.
- [x] 9. Measure coverage against real launch history before and after, and report the share of runs carrying usage rather than asserting the fix worked. Reconcile the corrected totals against the external ccusage tool run per session as HOME=<auth_home> npx ccusage --json — an independent reader of the same transcripts. Today the two differ by roughly 800x, so agreement is the strongest available evidence the fix landed.
- [x] 10. Keep the non-fatal guarantee under test throughout: no change here may turn a missing or unreadable transcript into a failed launch.
- [x] 11. Weight the token classes and rank by the result, once the fields are split and the deltas are correct. Record the weights as ratios relative to uncached input with the rationale beside them — they are provider ratios, not prices, which is why no per-model table is needed and why this cannot go stale.
- [x] 12. Leave currency last and separate. It needs the serving model per run, read from the transcript rather than inferred from the session's configured launch settings, and it is the one part of this request carrying a perishable input. Ship the weighted ranking without it if attribution proves harder than expected — the ranking is what makes the numbers actionable.
- [x] 13. Run the usage, status, and runs test files, then `logics-manager lint --require-status` and `logics-manager audit --group-by-doc` before closeout.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_126_define_one_token_accounting_shared_by_both_usage_readers`
- `item_127_bill_each_run_for_its_own_tokens_instead_of_the_whole_transcript`
- `item_128_read_usage_from_the_session_s_own_transcript_not_the_newest_file`
- `item_129_rank_sessions_by_weighted_cost_equivalent_tokens`
- `item_130_report_token_spend_in_currency`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: Claude total now covers cached input; `test_a_total_that_excludes_cache_is_not_produced` and the reader agreement fixtures. b73f5a5
- request-AC2 -> This task. Proof: `_summarize_stats` ranks on the weighted figure and derives TOTAL from the displayed columns; `StatsRankingTests`. 8fc3a1a, 55b08fd
- request-AC3 -> This task. Proof: A run stores the increment over the previous run on the same transcript; `test_the_runs_sum_to_the_transcript_total_not_a_multiple_of_it`. 3227d38
- request-AC4 -> This task. Proof: Resolution by conversation id; `test_a_newer_unrelated_transcript_does_not_win`. 996380f
- request-AC5 -> This task. Proof: Unresolvable or degenerate transcripts report absence and never raise; `test_a_known_id_with_no_transcript_reports_absence_not_a_guess`, `test_a_shrunken_transcript_reports_absence_rather_than_a_negative`. 996380f, 3227d38
- request-AC6 -> This task. Proof: IN is the uncached remainder on both providers; `test_headless_interactive_and_background_readers_agree` plus the Codex subset check. b73f5a5
- request-AC7 -> This task. Proof: All three readers normalize to one definition and carry the full field set; `UsageDefinitionAgreementTests`. b73f5a5
- request-AC8 -> This task. Proof: Coverage measured, not asserted: 12 of 13 claude/codex sessions carry a conversation id and all 12 resolve to an existing transcript, against 33 of 1006 runs carrying usage before. 996380f
- request-AC9 -> This task. Proof: The run registry normalizes on the way in via `coerce_usage`, so the JSON surfaces publish the shared shape; `test_commands_runs_py` payload assertions. b73f5a5
- request-AC10 -> This task. Proof: README documents every field, the weighting and the cost estimate; the 'never counted twice' claim is now true because IN excludes cache. b73f5a5, 8fc3a1a, 55b08fd
- request-AC11 -> This task. Proof: Cache creation and read are separate fields and the table ranks on the weighted figure; `test_a_cache_heavy_session_ranks_below_one_that_generated_more`. 8fc3a1a
- request-AC12 -> This task. Proof: The serving model is read from the transcript and priced from configurable prices; an unknown model stays unpriced. `CostEstimateTests`, `ModelAttributionTests`. 55b08fd

# Validation
- Wave A (plan steps 1-5), 2026-08-14: `npm test` 906 passed, `npm run lint` all checks passed. Baseline before the change was 898 passed.
- Wave B (plan steps 6-7), 2026-08-14: `npm test` 914 passed, `npm run lint` all checks passed.
- Wave C (plan steps 8-10), 2026-08-14: `npm test` 918 passed, `npm run lint` all checks passed.
- Wave D complete (plan steps 11-12), 2026-08-14: `npm test` 934 passed, `npm run lint` all checks passed, `logics-manager audit` 0 blocking and no non-deferred warnings.
- Wave D weighting (plan step 11), 2026-08-14: `npm test` 924 passed, `npm run lint` all checks passed.
- Coverage measured against the real store rather than asserted: before, 33 of 1006 recorded runs carried any usage (3.3%). After, 12 of 13 claude/codex sessions carry a conversation id and all 12 resolve to an existing transcript; only `work5` has no id, and it has not been launched in nine days. The post-change run-level share cannot be measured until runs accumulate under the new resolution.
- Oracle reconciliation on one real 2741-row Claude transcript, cdx reader against an independent reader of the same bytes: exact agreement on all four measured fields (input 3321, cache creation 2671168, cache read 797566574, output 820410). Before the de-duplication fix the same file read 1.55x high.
- command: `npm test && npm run lint` | result: passed | date: 2026-08-14
- Finish workflow executed on 2026-08-14.
- Linked backlog/request close verification passed.

# Report
- **Wave A delivered** in b73f5a5 and 878e570. One shared definition now lives in `src/run_usage.py` and all three readers normalize to it; cache creation and cache read are separate fields; IN is the uncached remainder on both providers; the total covers all four token classes; the run registry normalizes on the way in so the JSON surfaces publish the shared shape; the README documents the fields and no longer claims an invariant the code broke.
- **A fifth defect surfaced during implementation and was fixed here.** The interactive reader de-duplicated on the transcript row's `uuid`, but a Claude transcript records the same billed API response under several uuids -- 2741 rows for 1765 distinct responses on the file measured, so 36% were repeats. cdx over-reported that file by 1.55x. The billed unit is `(message id, request id)`; keying on it made cdx and the oracle agree exactly. The native-background reader had no de-duplication at all and now shares the same key. This was found only because the oracle check was in the plan; no test would have caught it.
- **An assumption was corrected rather than shipped.** The request stated that Codex counts cached tokens inside `input_tokens`. That holds for real records, but a test fixture carried `cached > input`, which cannot be a subset. Subtracting unconditionally would have erased real input tokens, so the reduction is now applied only when the subset relationship actually holds.
- **Wave B delivered** in 3227d38. A run now stores the increment over the previous run on the same transcript, with the cumulative kept beside it as `usage_cumulative` -- the next run's baseline, and the reason a single unmeasured run does not break the chain for every run after it. Codex is covered by the same code without a provider branch, because the delta is taken on the record the reader returns rather than inside either parser; a test asserts it rather than assuming it.
- **Degenerate transcripts report absence, never arithmetic.** A shrunk, rotated, or replaced transcript yields a negative component, so the whole delta is voided while the baseline still advances and the next run recovers. The first run against a transcript that predates it leaves a baseline and records nothing, because attributing an unmeasured history to one run is the same over-count the delta exists to prevent, committed once instead of N times.
- **A sixth defect fixed in passing:** the failure path in `handle_launch` called `_attach_interactive_usage` and discarded its return value, so a failed launch recorded no usage at all.
- **One scope item was found unnecessary rather than skipped.** `item_127` asked for delta handling on the native background path. It is not needed: `provider_session_id` is the agent id the provider assigns per `--bg` invocation (`src/commands/runs.py:322`), the agent is stopped at reconcile, and each run therefore reads a transcript created for it alone. There is nothing to accumulate, so the cumulative *is* the increment. Adding a baseline store there would solve a problem the code cannot reach.
- **Wave C delivered** in 996380f. Resolution is by conversation id, reusing `find_session_transcript` for Claude so one rule answers the question, and matching the id Codex repeats in its rollout filename. A session whose id resolves to nothing reports absence rather than falling back to the scan, because a wrong attribution is worse than a missing one — that fallback *was* the defect. The scan survives only for sessions with no id, and the record says which of the two produced the number (`provider_transcript_match`).
- **The scan's escape hatches were reporting guesses as measurements.** Exhausting the one-second deadline or the 1000-candidate cap used to return whichever candidate had been reached so far. Both now report absence.
- **The non-fatal guarantee held throughout**: every change here returns absence on failure, and no path added an exception to a launch.
- **The weighting half of wave D delivered** in 8fc3a1a. `cdx stats` gained a `COST~` column and now ranks on it: each token class weighted by its cost relative to one uncached input token (cache read 0.1x, cache write 1.25x, output 5x). Ratios rather than prices, so no per-model table exists to go stale. The five-minute cache-write TTL is assumed; a one-hour TTL costs 2x and nothing in a transcript distinguishes them, so long-TTL writes are under-weighted and the README says so rather than hiding it.
- **Currency (`item_130`) delivered** in 55b08fd. The blocker was attribution, not arithmetic: both providers record the serving model per message, so it is read from the transcript and stored on the run rather than inferred from the session's optional and usually-unset launch setting. Prices live in `CDX_TOKEN_PRICES` with a dated built-in default printed alongside the totals; an unknown model stays unpriced instead of being charged a default tier.
- **One AC met by an approximation, stated rather than hidden.** A run is priced at the model serving its most recent record instead of being split per model. Splitting exactly would restructure the stored record and the delta arithmetic for the request's least valuable and most perishable feature; the rule is documented in the README, carries a `ponytail:` comment naming the upgrade path, and is pinned by a test.
- **A seventh defect, found by running the real command.** `cdx stats` summed each run's *stored* total, mixing pre-definition records that excluded cache with correct ones. On real data that produced a row contradicting itself: CACHE at 206.6M beside a TOTAL of 2.3M. Each row's total is now derived from the columns it displays, so a row always adds up while history spans both eras. Legacy records carry no creation/read split, so their fused cached figure is read as cache reads for weighting — the class that dominates it — and they stay unpriced.
- **Out of scope, fixed anyway because it blocked honest verification:** `test_runtime_py.py::test_non_interactive_and_non_claude_specs_keep_claude_title_writes_untouched` read the ambient environment and failed inside any Claude Code session. Fixed in 5bf4389 and committed separately; the suite now passes without an `env -u` workaround. `cdx stats` still shows historical figures for runs already in launch history: repairing those is explicitly out of scope for `item_127`.
- Out of scope, worth its own request: `test_runtime_py.py::test_non_interactive_and_non_claude_specs_keep_claude_title_writes_untouched` reads the ambient environment, so it fails whenever the suite runs inside a Claude Code session (which exports `CLAUDE_CODE_DISABLE_TERMINAL_TITLE`). It passes under `env -u CLAUDE_CODE_DISABLE_TERMINAL_TITLE`. Pre-existing, unrelated to this task.
- Finished on 2026-08-14.
- Linked backlog item(s): `item_126_define_one_token_accounting_shared_by_both_usage_readers`, `item_127_bill_each_run_for_its_own_tokens_instead_of_the_whole_transcript`, `item_128_read_usage_from_the_session_s_own_transcript_not_the_newest_file`, `item_129_rank_sessions_by_weighted_cost_equivalent_tokens`, `item_130_report_token_spend_in_currency`
- Related request(s): `req_063_make_cdx_stats_report_the_tokens_a_session_actually_spent`

# Links
- Request: `req_063_make_cdx_stats_report_the_tokens_a_session_actually_spent`
- Product brief(s): `prod_049_token_numbers_a_user_can_act_on`
- Architecture decision(s): (none yet)
