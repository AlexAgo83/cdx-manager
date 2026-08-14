## item_127_bill_each_run_for_its_own_tokens_instead_of_the_whole_transcript - Bill each run for its own tokens instead of the whole transcript
> From version: 0.19.3
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: High
> Theme: Usage accounting
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: bill, each, run, own, tokens, instead, whole, transcript
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- `_claude_usage` sums every assistant message in the transcript file, so its return is the session's running total, not the run's.
- `_attach_interactive_usage` stores that running total as the run's `usage`, and `_summarize_stats` sums the stored usage across runs. A session resumed N times therefore contributes its history roughly N times over.
- The observed jump — one extra run moving CACHE from 2.6M to 7.6M and OUT from 44.0K to 88.9K — is this behavior, not an anomaly.
- `_codex_usage` takes the last `total_token_usage`, which is also cumulative for the conversation, so the same defect applies to resumed Codex sessions.
- `provider_transcript_path` is already written into each run entry and never read, so the information needed to compute a delta is recorded but unused.

# Scope
- In:
  - Make the usage stored on a run entry the increment attributable to that run.
  - Derive the increment from the previous run's recorded cumulative for the same transcript — the launch history already carries `provider_transcript_path` — or by bounding the transcript read to records written after the run started, whichever proves reliable for both providers.
  - Keep the cumulative alongside the delta if the delta cannot be derived without it, so a later run has a baseline even when an intermediate run recorded nothing.
  - Handle the transcript shrinking, being rotated, or being replaced without producing a negative or absurd delta — clamp and record absence rather than emitting a wrong number.
  - Handle the first run on a pre-existing transcript, where there is no prior baseline, in a stated way rather than by accident.
  - Apply the same treatment to `_codex_usage`, whose `total_token_usage` is cumulative per conversation.
  - Add tests driving two consecutive runs over a growing transcript fixture and asserting the second run records only the growth, and that the runs sum to the transcript total.
- Out:
  - No repair of usage already stored in existing launch history.
  - No change to the launch history schema beyond what recording a delta requires.
  - No change to the arithmetic definitions settled in the first item.

# Acceptance criteria
- Given a transcript that grows by a known amount between two launches, the second run's recorded usage equals that growth.
- Given those two runs, `cdx stats` reports a total equal to the transcript's total, not a multiple of it.
- Given a resumed session launched three times over one conversation, the summed stats equal the conversation's consumption once.
- Given a transcript that shrank or was replaced since the previous run, no negative or inflated delta is recorded and the run reports absence instead.
- Given a first run against a transcript that already existed, the documented rule is applied and asserted by a test naming the expected recorded value.
- Given a Codex conversation resumed twice, the second run records only the increment of `total_token_usage`.

# AC Traceability
- request-AC3 -> This backlog slice. Proof: Given a transcript that grows by a known amount between two launches, the second run's recorded usage equals that growth.
- request-AC5 -> This backlog slice. Proof: Given those two runs, `cdx stats` reports a total equal to the transcript's total, not a multiple of it.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_049_token_numbers_a_user_can_act_on`
- Architecture decision(s): (none yet)
- Request: `req_063_make_cdx_stats_report_the_tokens_a_session_actually_spent`
- Primary task(s): `task_073_orchestrate_truthful_token_accounting_for_cdx_stats`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
