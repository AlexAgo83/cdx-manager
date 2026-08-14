## item_126_define_one_token_accounting_shared_by_both_usage_readers - Define one token accounting shared by both usage readers
> From version: 0.19.3
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Usage accounting
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-14 10:19:18

# AI Context
- Summary: Three readers each encode their own arithmetic for the same five token fields; this slice writes one definition and normalizes all of them to it, including the published JSON surfaces.
- Keywords: token accounting, cached_input_tokens, run_usage, interactive_usage, provider_background, run registry, normalized usage
- Use when: Changing the meaning, arithmetic, or field set of a cdx usage record.
- Skip when: Changing which transcript is read or what a run stores — those are `item_128` and `item_127`.

# Problem
- `_claude_usage` computes `total_tokens = input_tokens + output_tokens` (`src/interactive_usage.py:104`), silently dropping cache creation and cache reads from the only figure the table headlines and sorts by.
- `_usage_from_dict` (`src/run_usage.py:80`) makes the opposite mistake: it adds the cache fields into `input_tokens` *and* reports them again as `cached_input_tokens`, so IN and CACHE overlap for headless runs while they are disjoint for interactive ones.
- `read_transcript_outcome` (`src/provider_background.py:213`) is a third reader with a fourth variant: it folds the cache into `input_tokens`, emits no `cached_input_tokens` key at all, and so produces a cache-inclusive total. A detached Claude run and an interactive one from the same session therefore populate the same TOTAL column under opposite definitions, and the detached run leaves CACHE empty.
- Codex's `total_token_usage.input_tokens` is cache-inclusive by construction, Claude's is not, and both land in the same IN column with no marker.
- `README.md:711` already asserts that cached input "is never counted twice", an invariant `run_usage` violates today, so the documentation and the code disagree about which definition is in force.
- These fields are published, not internal: `cdx run --json` (`src/run_command.py:212`), `cdx run-status`, and `cdx run-report` (`src/commands/runs.py:483`) emit them, and `src/run_registry.py:318` stores whatever the producing reader emitted without normalizing.
- There is no written definition of what each field means, so each reader encodes its own guess and no surface can be checked against anything.

# Scope
- In:
  - Write down, once and in code, what `input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_tokens`, and `total_tokens` mean in a cdx usage record — in particular whether IN includes cache and whether TOTAL includes it.
  - Normalize all three readers to that definition: `src/run_usage.py`, `src/interactive_usage.py`, and `src/provider_background.py`. Fold the background reader's arithmetic into the shared one rather than leaving a fourth copy behind.
  - Guarantee every usage record carries the full field set, so `cached_input_tokens` is never structurally absent depending on which path produced the run.
  - Normalize Claude and Codex records to that definition, adjusting whichever provider does not already match rather than leaving the difference for the table to paper over.
  - Fix `total_tokens` for Claude to cover cached input, and remove the within-record cache double count in `run_usage._usage_from_dict`.
  - Confirm `_summarize_stats` sorts by the corrected total and that the sort key is the same number the TOTAL column prints.
  - Normalize on the way into the run registry (`src/run_registry.py:318`) so the JSON surfaces publish the shared shape rather than the producing reader's shape.
  - Update the README where it describes token usage: the column meanings alongside `cdx stats`, the "never counted twice" claim at `README.md:711`, and the headless-only description at `README.md:540`.
  - Add tests over recorded fixture records from all three readers and both providers asserting the normalized fields, including a case where cache reads dominate the total.
  - Reconcile the corrected numbers against the external ccusage tool as an independent oracle over the same transcripts, scoped to one session with HOME=<auth_home> npx ccusage --json, and record the comparison in the slice report. Verification only — no runtime dependency on it.
- Out:
  - No change to which transcript is read or to what a run stores — those are separate items.
  - No new columns and no change to the table layout.
  - No currency conversion or pricing.
  - No change to the `CDX_EXPERIMENTAL_NATIVE_BG` gating or to how background runs are dispatched.

# Acceptance criteria
- Given a Claude record with uncached input, cache creation, cache reads, and output, the normalized total covers all four rather than only uncached input plus output.
- Given a headless Claude record, IN and CACHE do not both count the same cache tokens.
- Given the same consumption read by the headless, interactive, and native-background readers, all three produce identical normalized records.
- Given a native background run, its usage record carries `cached_input_tokens` rather than omitting the key, and its total uses the same definition as an interactive run of the same session.
- Given equivalent consumption reported by Codex and by Claude, the normalized records agree field by field.
- Given a set of sessions, the stats table orders them by the same total it prints.
- Given a completed run, the usage in `cdx run --json`, `cdx run-status --json`, and `cdx run-report --json` matches what `cdx stats` counts for that run.
- The README defines each stats column, stating explicitly whether IN and TOTAL include cached input, and no surviving README claim about token usage contradicts the code.
- A test asserts the definition across all three readers and both providers from fixture records, and fails if any reader drifts from it.
- Given one Claude session's transcripts, the input, cache-creation, cache-read, and output totals cdx reports for it agree with what that tool reports over the same files, and any residual difference is explained rather than tolerated.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: Given a Claude record with uncached input, cache creation, cache reads, and output, the normalized total covers all four rather than only uncached input plus output.
- request-AC2 -> This backlog slice. Proof: Given a set of sessions, the stats table orders them by the same total it prints.
- request-AC6 -> This backlog slice. Proof: Given equivalent consumption reported by Codex and by Claude, the normalized records agree field by field.
- request-AC7 -> This backlog slice. Proof: Given the same consumption read by the headless, interactive, and native-background readers, all three produce identical normalized records.
- request-AC9 -> This backlog slice. Proof: Given a completed run, the usage in `cdx run --json`, `cdx run-status --json`, and `cdx run-report --json` matches what `cdx stats` counts for that run.
- request-AC10 -> This backlog slice. Proof: The README defines each stats column, stating explicitly whether IN and TOTAL include cached input, and no surviving README claim about token usage contradicts the code.

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
