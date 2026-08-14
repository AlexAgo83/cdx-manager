## item_132_drop_token_usage_cdx_cannot_vouch_for - Drop token usage cdx cannot vouch for
> From version: 0.19.3
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 95%
> Progress: 100%
> Complexity: High
> Theme: Operator workflow and runtime integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-14 14:33:23

# AI Context
- Summary: Usage recorded before the field definition is excluded from every total automatically, and cdx repair clears it from the file for anyone who wants that.
- Keywords: launch history, legacy usage, cdx repair, is_vouched, cdx stats
- Use when: Changing what cdx does with usage figures it cannot substantiate.
- Skip when: Changing how new usage is measured.

# Problem
`cdx stats` still reports figures that are not merely imprecise but fictitious, and it reports them with the same authority as correct ones. On a real store, `digital` shows 206.6M cached tokens for a period in which its own conversation consumed 33,608 -- four orders of magnitude, and the number rises every time somebody reads it as real.
Two defects compounded to produce those records. The reader picked whichever transcript in the provider home had the newest mtime, so a run was billed against an unrelated project's file; and it re-read that whole file on every launch, so consecutive runs recorded 33,544 then 5,044,782 then 198,926,945 for the same session.
Both defects are fixed, and every run recorded since is correct. What remains is a body of stored records that will keep polluting every `cdx stats` window until it ages out of the periods people ask for -- which for a `--since 30d` view is a month of wrong answers, and for an unbounded view is forever.
A user cannot tell the two eras apart from the output. Old and new records sum into one column, so the table is neither wholly wrong nor trustworthy, which is the worst of the three available states.

# Scope
- In:
  - Mark such records by the absence of `cache_creation_tokens`, which `normalize_usage` always emits and nothing before it did -- not by the absence of `usage_cumulative`, which headless runs legitimately lack.
  - Exclude them from every aggregate automatically, and report how many runs that covered so the exclusion is visible.
  - Filter rather than mutate, so the records stay recoverable if the marker ever proves wrong.
  - Offer `cdx repair` for operators who want the file itself cleaned, with the same dry-run contract as the rest of that command.
- Out:
  - No recomputation of past figures from current transcripts: that would invent a distribution.
  - No change to the fields themselves.

# Acceptance criteria
- Given a record written before the definition, no total includes it and the run itself -- status, duration, timestamp -- survives.
- Given a mixed history, vouched records in the same session still count.
- Given a headless record, which carries no cumulative, it is not mistaken for a legacy one.
- Given any exclusion, the output says how many runs it covered.
- Given `cdx repair`, the stored records are cleared, and nothing else depends on that having been run.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: Given a record written before the definition, no total includes it and the run itself -- status, duration, timestamp -- survives.
- request-AC2 -> This backlog slice. Proof: Given a mixed history, vouched records in the same session still count.
- request-AC3 -> This backlog slice. Proof: Given a headless record, which carries no cumulative, it is not mistaken for a legacy one.
- request-AC4 -> This backlog slice. Proof: Given any exclusion, the output says how many runs it covered.
- request-AC5 -> This backlog slice. Proof: Given a record written before the definition, no total includes it without anyone running a command, and the output says how many runs were excluded.
- request-AC6 -> This backlog slice. Proof: Given a period containing only such runs, the totals report absence rather than zero, because the excluded usage never enters the sum.
- request-AC7 -> This backlog slice. Proof: The records are filtered rather than mutated, and `cdx repair` clears the file for anyone who wants that without anything depending on it.

# Decision framing
- Product framing: Not needed
- Product signals: (none detected)
- Product follow-up: No product brief follow-up is expected based on current signals.
- Architecture framing: Not needed
- Architecture signals: (none detected)
- Architecture follow-up: No architecture decision follow-up is expected based on current signals.

# Links
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
- Request: `req_065_drop_token_usage_cdx_cannot_vouch_for`
- Primary task(s): `task_075_drop_token_usage_cdx_cannot_vouch_for`

# Priority
- Priority: Medium
- Rationale: Default until groomed.

# Notes
- Hybrid rationale: Derived from request `req_065_drop_token_usage_cdx_cannot_vouch_for` and kept bounded to one coherent delivery slice.
- Source file: `logics/request/req_065_drop_token_usage_cdx_cannot_vouch_for.md`.
- Generated locally by logics-manager.
- Task `task_075_drop_token_usage_cdx_cannot_vouch_for` was finished via `logics-manager flow finish task` on 2026-08-14.

# Tasks
- `task_075_drop_token_usage_cdx_cannot_vouch_for`
