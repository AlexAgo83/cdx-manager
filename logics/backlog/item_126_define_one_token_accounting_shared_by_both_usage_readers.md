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

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: define, token, accounting, shared, both, usage, readers
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- `_claude_usage` computes `total_tokens = input_tokens + output_tokens` (`src/interactive_usage.py:104`), silently dropping cache creation and cache reads from the only figure the table headlines and sorts by.
- `_usage_from_dict` (`src/run_usage.py:80`) makes the opposite mistake: it adds the cache fields into `input_tokens` *and* reports them again as `cached_input_tokens`, so IN and CACHE overlap for headless runs while they are disjoint for interactive ones.
- Codex's `total_token_usage.input_tokens` is cache-inclusive by construction, Claude's is not, and both land in the same IN column with no marker.
- There is no written definition of what each of the four columns means, so each reader encodes its own guess.

# Scope
- In:
  - Write down, once and in code, what `input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_tokens`, and `total_tokens` mean in a cdx usage record — in particular whether IN includes cache and whether TOTAL includes it.
  - Normalize Claude and Codex records to that definition, adjusting whichever provider does not already match rather than leaving the difference for the table to paper over.
  - Fix `total_tokens` for Claude to cover cached input, and remove the within-record cache double count in `run_usage._usage_from_dict`.
  - Confirm `_summarize_stats` sorts by the corrected total and that the sort key is the same number the TOTAL column prints.
  - Document the column meanings in the README alongside `cdx stats`.
  - Add tests over recorded fixture records from both providers asserting the normalized fields, including a case where cache reads dominate the total.
- Out:
  - No change to which transcript is read or to what a run stores — those are separate items.
  - No new columns and no change to the table layout.
  - No currency conversion or pricing.

# Acceptance criteria
- Given a Claude record with uncached input, cache creation, cache reads, and output, the normalized total covers all four rather than only uncached input plus output.
- Given a headless Claude record, IN and CACHE do not both count the same cache tokens.
- Given equivalent consumption reported by Codex and by Claude, the normalized records agree field by field.
- Given a set of sessions, the stats table orders them by the same total it prints.
- The README defines each stats column, stating explicitly whether IN and TOTAL include cached input.
- A test asserts the definition for both providers from fixture records, and fails if either reader drifts from it.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: Given a Claude record with uncached input, cache creation, cache reads, and output, the normalized total covers all four rather than only uncached input plus output.
- request-AC2 -> This backlog slice. Proof: Given a headless Claude record, IN and CACHE do not both count the same cache tokens.
- request-AC6 -> This backlog slice. Proof: Given equivalent consumption reported by Codex and by Claude, the normalized records agree field by field.
- request-AC7 -> This backlog slice. Proof: Given a set of sessions, the stats table orders them by the same total it prints.

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
