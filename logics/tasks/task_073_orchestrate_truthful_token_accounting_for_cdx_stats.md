## task_073_orchestrate_truthful_token_accounting_for_cdx_stats - Orchestrate truthful token accounting for cdx stats
> From version: 0.19.3
> Schema version: 1.0
> Status: In progress
> Understanding: 95%
> Confidence: 90%
> Progress: 40%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-14 10:26:32
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
- [ ] 6. Then fix what a run stores. The delta work depends on the definitions being settled, and it is the change that actually stops the numbers inflating on resume. Use the already-recorded `provider_transcript_path` as the anchor, establish an equivalent anchor for the background path which has none, and decide explicitly what a first run against a pre-existing transcript records.
- [ ] 7. Handle the degenerate transcript cases — shrunk, rotated, replaced — as absence rather than as arithmetic. A missing number is recoverable; a wrong one is not.
- [ ] 8. Replace the mtime guess with conversation-id resolution last, so the delta tests are already green and any coverage change is attributable to this step alone. Reuse `find_session_transcript` (`src/provider_background.py:193`), which already does this for the background path — the outcome is one resolver, not a better second one.
- [ ] 9. Measure coverage against real launch history before and after, and report the share of runs carrying usage rather than asserting the fix worked. Reconcile the corrected totals against the external ccusage tool run per session as HOME=<auth_home> npx ccusage --json — an independent reader of the same transcripts. Today the two differ by roughly 800x, so agreement is the strongest available evidence the fix landed.
- [ ] 10. Keep the non-fatal guarantee under test throughout: no change here may turn a missing or unreadable transcript into a failed launch.
- [ ] 11. Weight the token classes and rank by the result, once the fields are split and the deltas are correct. Record the weights as ratios relative to uncached input with the rationale beside them — they are provider ratios, not prices, which is why no per-model table is needed and why this cannot go stale.
- [ ] 12. Leave currency last and separate. It needs the serving model per run, read from the transcript rather than inferred from the session's configured launch settings, and it is the one part of this request carrying a perishable input. Ship the weighted ranking without it if attribution proves harder than expected — the ranking is what makes the numbers actionable.
- [ ] 13. Run the usage, status, and runs test files, then `logics-manager lint --require-status` and `logics-manager audit --group-by-doc` before closeout.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_126_define_one_token_accounting_shared_by_both_usage_readers`
- `item_127_bill_each_run_for_its_own_tokens_instead_of_the_whole_transcript`
- `item_128_read_usage_from_the_session_s_own_transcript_not_the_newest_file`
- `item_129_rank_sessions_by_weighted_cost_equivalent_tokens`
- `item_130_report_token_spend_in_currency`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_126_define_one_token_accounting_shared_by_both_usage_readers`. Proof deferred to slice closeout.
- request-AC2 -> `item_126_define_one_token_accounting_shared_by_both_usage_readers`. Proof deferred to slice closeout.
- request-AC6 -> `item_126_define_one_token_accounting_shared_by_both_usage_readers`. Proof deferred to slice closeout.
- request-AC7 -> `item_126_define_one_token_accounting_shared_by_both_usage_readers`. Proof deferred to slice closeout.
- request-AC3 -> `item_127_bill_each_run_for_its_own_tokens_instead_of_the_whole_transcript`. Proof deferred to slice closeout.
- request-AC5 -> `item_127_bill_each_run_for_its_own_tokens_instead_of_the_whole_transcript`. Proof deferred to slice closeout.
- request-AC4 -> `item_128_read_usage_from_the_session_s_own_transcript_not_the_newest_file`. Proof deferred to slice closeout.
- request-AC5 -> `item_128_read_usage_from_the_session_s_own_transcript_not_the_newest_file`. Proof deferred to slice closeout.
- request-AC8 -> `item_128_read_usage_from_the_session_s_own_transcript_not_the_newest_file`. Proof deferred to slice closeout.
- request-AC9 -> `item_126_define_one_token_accounting_shared_by_both_usage_readers`. Proof deferred to slice closeout.
- request-AC10 -> `item_126_define_one_token_accounting_shared_by_both_usage_readers`. Proof deferred to slice closeout.
- request-AC11 -> `item_129_rank_sessions_by_weighted_cost_equivalent_tokens`. Proof deferred to slice closeout.
- request-AC12 -> `item_130_report_token_spend_in_currency`. Proof deferred to slice closeout.

# Validation
- Wave A (plan steps 1-5), 2026-08-14: `npm test` 906 passed, `npm run lint` all checks passed. Baseline before the change was 898 passed.
- Oracle reconciliation on one real 2741-row Claude transcript, cdx reader against an independent reader of the same bytes: exact agreement on all four measured fields (input 3321, cache creation 2671168, cache read 797566574, output 820410). Before the de-duplication fix the same file read 1.55x high.

# Report
- **Wave A delivered** in b73f5a5 and 878e570. One shared definition now lives in `src/run_usage.py` and all three readers normalize to it; cache creation and cache read are separate fields; IN is the uncached remainder on both providers; the total covers all four token classes; the run registry normalizes on the way in so the JSON surfaces publish the shared shape; the README documents the fields and no longer claims an invariant the code broke.
- **A fifth defect surfaced during implementation and was fixed here.** The interactive reader de-duplicated on the transcript row's `uuid`, but a Claude transcript records the same billed API response under several uuids -- 2741 rows for 1765 distinct responses on the file measured, so 36% were repeats. cdx over-reported that file by 1.55x. The billed unit is `(message id, request id)`; keying on it made cdx and the oracle agree exactly. The native-background reader had no de-duplication at all and now shares the same key. This was found only because the oracle check was in the plan; no test would have caught it.
- **An assumption was corrected rather than shipped.** The request stated that Codex counts cached tokens inside `input_tokens`. That holds for real records, but a test fixture carried `cached > input`, which cannot be a subset. Subtracting unconditionally would have erased real input tokens, so the reduction is now applied only when the subset relationship actually holds.
- Waves B, C and D (per-run deltas, transcript resolution by conversation id, weighting and currency) are untouched. `cdx stats` still shows historical figures for runs already in launch history: repairing those is explicitly out of scope for `item_127`.
- Out of scope, worth its own request: `test_runtime_py.py::test_non_interactive_and_non_claude_specs_keep_claude_title_writes_untouched` reads the ambient environment, so it fails whenever the suite runs inside a Claude Code session (which exports `CLAUDE_CODE_DISABLE_TERMINAL_TITLE`). It passes under `env -u CLAUDE_CODE_DISABLE_TERMINAL_TITLE`. Pre-existing, unrelated to this task.

# Links
- Request: `req_063_make_cdx_stats_report_the_tokens_a_session_actually_spent`
- Product brief(s): `prod_049_token_numbers_a_user_can_act_on`
- Architecture decision(s): (none yet)
