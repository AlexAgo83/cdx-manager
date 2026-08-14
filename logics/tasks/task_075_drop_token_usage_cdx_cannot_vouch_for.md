## task_075_drop_token_usage_cdx_cannot_vouch_for - Drop token usage cdx cannot vouch for
> From version: 0.19.3
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 95%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-14 14:33:24

# AI Context
- Summary: Usage cdx cannot substantiate is excluded from every total automatically; cdx repair clears it from the file for those who want that.
- Keywords: launch history, legacy usage, is_vouched, cdx repair, 0.20.0
- Use when: Revisiting this change.
- Skip when: Working on unrelated cdx surfaces.

# Definition of Done (DoD)
- [x] The backlog scope is implemented.
- [x] Acceptance criteria are covered.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# Backlog
- `item_132_drop_token_usage_cdx_cannot_vouch_for`

# Acceptance criteria
- Given a record written before the definition, no total includes it and the run itself -- status, duration, timestamp -- survives.
- Given a mixed history, vouched records in the same session still count.
- Given a headless record, which carries no cumulative, it is not mistaken for a legacy one.
- Given any exclusion, the output says how many runs it covered.
- Given `cdx repair`, the stored records are cleared, and nothing else depends on that having been run.

# Plan
- [x] 1. Mark unvouched records by the absence of `cache_creation_tokens`, not of `usage_cumulative`.
- [x] 2. Exclude them from every aggregate automatically and report how many runs that covered.
- [x] 3. Filter rather than mutate, so the records stay recoverable.
- [x] 4. Add `cdx repair` support for clearing them from the file, with the existing dry-run contract.
- [x] GATE: delivered, validated, and shipped in 0.20.0.

# AC Traceability
- request-AC1 -> This task. Proof: `test_legacy_usage_goes_and_the_run_stays` and `test_unvouched_usage_is_excluded_without_anyone_running_a_command`. 897d810, 68f2325
- request-AC2 -> This task. Proof: `test_vouched_usage_in_the_same_session_still_counts`. 68f2325
- request-AC3 -> This task. Proof: `test_a_headless_record_is_not_mistaken_for_a_legacy_one`. 897d810
- request-AC4 -> This task. Proof: `test_the_exclusion_is_counted_so_it_is_not_silent`, and the totals line names the excluded runs. 68f2325
- request-AC5 -> This task. Proof: `test_a_dry_run_counts_without_touching_anything` and `test_a_mixed_history_drops_only_the_unvouched_half`. 897d810
- request-AC6 -> This task. Proof: A period holding only such runs sums to nothing, because the excluded usage never enters the total. 68f2325
- request-AC7 -> This task. Proof: `test_the_stored_record_is_left_alone` asserts the filter does not mutate. 68f2325

# Validation
- 2026-08-14: `npm test` 968 passed, `npm run lint` all checks passed, GitHub CI green on Linux, macOS and Windows.
- On the operator's real store: `cdx repair --dry-run` reports 36 of 1027 records carrying unvouched usage, and `digital` falls from 206.6M cached tokens to 361.3K once they are excluded, with the totals line naming four excluded runs.
- command: `npm test && npm run lint` | result: passed | date: 2026-08-14
- Finish workflow executed on 2026-08-14.
- Linked backlog/request close verification passed.

# Report
- Delivered in 897d810 and 68f2325; shipped in 0.20.0.
- The request first required an explicit command and argued that filtering at read time would be too silent. That was corrected during implementation: an upgrade would have left the fictitious figures on screen until somebody remembered `cdx repair`, and a filter can perfectly well announce itself -- which this one does.
- Filtering rather than mutating was the second correction. It keeps the records recoverable if the marker ever proves wrong, and makes `cdx repair` optional rather than load-bearing.
- Finished on 2026-08-14.
- Linked backlog item(s): `item_132_drop_token_usage_cdx_cannot_vouch_for`
- Related request(s): `req_065_drop_token_usage_cdx_cannot_vouch_for`

# Links
- Request: `req_065_drop_token_usage_cdx_cannot_vouch_for`
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
