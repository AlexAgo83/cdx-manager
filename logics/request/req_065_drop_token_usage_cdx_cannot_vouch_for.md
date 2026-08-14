## req_065_drop_token_usage_cdx_cannot_vouch_for - Drop token usage cdx cannot vouch for
> From version: 0.19.3
> Schema version: 1.0
> Status: Done
> Understanding: 90
> Confidence: 85
> Complexity: Medium
> Theme: Usage accounting
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-14 14:33:23

# AI Context
- Summary: Launch history written before the usage definition existed is wrong by four orders of magnitude and cannot be recomputed, so it should be dropped rather than displayed.
- Keywords: launch history, legacy usage records, cdx stats, purge, repair, retroactive
- Use when: Deciding what to do with usage figures recorded before the accounting was corrected.
- Skip when: Changing how new usage is measured -- that work is done.

# Needs
- `cdx stats` still reports figures that are not merely imprecise but fictitious, and it reports them with the same authority as correct ones. On a real store, `digital` shows 206.6M cached tokens for a period in which its own conversation consumed 33,608 -- four orders of magnitude, and the number rises every time somebody reads it as real.
- Two defects compounded to produce those records. The reader picked whichever transcript in the provider home had the newest mtime, so a run was billed against an unrelated project's file; and it re-read that whole file on every launch, so consecutive runs recorded 33,544 then 5,044,782 then 198,926,945 for the same session.
- Both defects are fixed, and every run recorded since is correct. What remains is a body of stored records that will keep polluting every `cdx stats` window until it ages out of the periods people ask for -- which for a `--since 30d` view is a month of wrong answers, and for an unbounded view is forever.
- A user cannot tell the two eras apart from the output. Old and new records sum into one column, so the table is neither wholly wrong nor trustworthy, which is the worst of the three available states.
# Context
- Recomputing is not available. A run's true usage is the increment its transcript gained while it ran, and reconstructing that needs the transcript's state at that moment -- which nothing recorded. Attributing today's totals to past runs would invent a distribution, replacing a wrong number with a fabricated one.
- **Corrected after implementing.** This request first said the drop must not happen silently at read time, and reasoned that an explicit command was therefore required. That was the wrong trade: displaying a fictitious figure is worse than filtering it, and a filter can perfectly well announce itself. Filtering is now automatic and states how many runs it excluded; `cdx repair` still exists for cleaning the file. An upgrade that left the fiction on screen until somebody remembered a command would have missed the point of the request.
- Dropping is available and precise. Records written before the definition existed lack the `cache_creation_tokens` key entirely, because `normalize_usage` emits the full field set and nothing else does. That is an exact discriminator, not a date heuristic.
- Do not key the discriminator on `usage_cumulative`: headless runs legitimately have none, and using it would drop correct records.
- The table already distinguishes runs with usage from runs without: the `USAGE` column counts them. A dropped record therefore reads as an honest absence rather than as a zero, and the drop is visible rather than silent.
- `src/repair.py` exists and is where cdx already performs one-shot repairs to its own home, so this needs no new surface of its own.
- The cost is real and should be stated: historical token totals disappear from `cdx stats`. They are wrong by four orders of magnitude, so losing them is a gain, but a user who had been reading them will notice.
# Delivery
- Delivered in 897d810 (`cdx repair` drops the figures from the file) and 68f2325 (they are excluded from every total automatically, which is what AC5 was corrected to require). Shipped in 0.20.0.
- Validated with `npm test` and `npm run lint`, and on the operator's real store: `cdx repair --dry-run` reports 36 of 1027 records carrying unvouched usage, and `digital` falls from 206.6M cached tokens to 361.3K once they are excluded, with the totals line naming how many runs that covered.
- The stored records are filtered rather than mutated, so `cdx repair` remains optional: it cleans the file for anyone who wants that, but nothing depends on it being run.

# Acceptance criteria
- AC1: Usage recorded before the field definition existed is no longer reported by `cdx stats`, `cdx history`, or the JSON surfaces.
- AC2: Runs, durations, statuses, and timestamps survive the drop; only the usage figures go. A run that happened still happened.
- AC3: Records written after the fix are untouched, identified by the presence of the full field set rather than by a date.
- AC4: Headless records, which legitimately carry no cumulative, are not mistaken for legacy ones.
- AC5: Unvouched usage is excluded automatically, without waiting for anyone to run a command -- an upgrade must not leave the fiction on screen -- and the exclusion says so, naming how many runs it covers.
- AC7: The stored records are not mutated to achieve AC5. Filtering at read time keeps them recoverable if the discriminator ever proves wrong, and `cdx repair` remains available for operators who want the file itself cleaned.
- AC6: `cdx stats` for a period containing only legacy runs reports absence rather than zero, so nothing reads as a session that spent nothing.
# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# References
- src/repair.py
- src/session_store.py
- src/commands/status.py
- src/run_usage.py
- test/test_commands_status_py.py

# Backlog
- `item_132_drop_token_usage_cdx_cannot_vouch_for`
