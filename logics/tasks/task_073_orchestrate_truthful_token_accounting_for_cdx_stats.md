## task_073_orchestrate_truthful_token_accounting_for_cdx_stats - Orchestrate truthful token accounting for cdx stats
> From version: 0.19.3
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-14 10:19:18

# AI Context
- Summary: Sequences the three slices so definitions land before arithmetic, arithmetic before per-run deltas, and transcript resolution last, keeping each behavior change attributable to one step.
- Keywords: token accounting, cdx stats, usage readers, per-run delta, transcript resolution, coverage measurement
- Use when: Implementing or sequencing any part of `req_063`.
- Skip when: Working on provider rate limits, credits, or quota display.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Inventory every producer and consumer of a usage record before changing any of them. Producers: `run_usage`, `interactive_usage`, `provider_background`. Consumers: the stats table, the run registry, and the `cdx run` / `run-status` / `run-report` JSON payloads. The third producer was missed on the first pass of this request; assume the inventory is the deliverable, not a formality.
- [ ] 2. Capture the current behavior as fixtures: a real Claude transcript with cache-heavy records, a Codex rollout with several `token_count` events, a native background close-out, and a growing-transcript pair simulating a resume. Record what each of today's three readers returns, so every later change has a baseline rather than an intention.
- [ ] 3. Settle the field definitions before touching any reader — whether IN and TOTAL include cached input — and write the decision down in code and README. All three readers and both providers then normalize to that one definition; do not let the table reconcile a difference the readers should have resolved.
- [ ] 4. Fix the arithmetic: Claude's total to cover cached input, the within-record cache double count in `run_usage._usage_from_dict`, and `provider_background`'s missing `cached_input_tokens` and inverted total. Confirm the stats sort key is the same number the TOTAL column prints.
- [ ] 5. Normalize at the run registry boundary so the JSON surfaces publish the shared shape, then reconcile the README's token claims — the column meanings, the "never counted twice" invariant at `README.md:711`, and the headless-only description at `README.md:540` — against what the code now does.
- [ ] 6. Then fix what a run stores. The delta work depends on the definitions being settled, and it is the change that actually stops the numbers inflating on resume. Use the already-recorded `provider_transcript_path` as the anchor, establish an equivalent anchor for the background path which has none, and decide explicitly what a first run against a pre-existing transcript records.
- [ ] 7. Handle the degenerate transcript cases — shrunk, rotated, replaced — as absence rather than as arithmetic. A missing number is recoverable; a wrong one is not.
- [ ] 8. Replace the mtime guess with conversation-id resolution last, so the delta tests are already green and any coverage change is attributable to this step alone. Reuse `find_session_transcript` (`src/provider_background.py:193`), which already does this for the background path — the outcome is one resolver, not a better second one.
- [ ] 9. Measure coverage against real launch history before and after, and report the share of runs carrying usage rather than asserting the fix worked. Reconcile the corrected totals against the external ccusage tool run per session as HOME=<auth_home> npx ccusage --json — an independent reader of the same transcripts. Today the two differ by roughly 800x, so agreement is the strongest available evidence the fix landed.
- [ ] 10. Keep the non-fatal guarantee under test throughout: no change here may turn a missing or unreadable transcript into a failed launch.
- [ ] 11. Run the usage, status, and runs test files, then `logics-manager lint --require-status` and `logics-manager audit --group-by-doc` before closeout.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_126_define_one_token_accounting_shared_by_both_usage_readers`
- `item_127_bill_each_run_for_its_own_tokens_instead_of_the_whole_transcript`
- `item_128_read_usage_from_the_session_s_own_transcript_not_the_newest_file`

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

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_063_make_cdx_stats_report_the_tokens_a_session_actually_spent`
- Product brief(s): `prod_049_token_numbers_a_user_can_act_on`
- Architecture decision(s): (none yet)
