## item_128_read_usage_from_the_session_s_own_transcript_not_the_newest_file - Read usage from the session's own transcript, not the newest file
> From version: 0.19.3
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 90%
> Progress: 100%
> Complexity: Medium
> Theme: Usage accounting
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-14 12:13:18

# AI Context
- Summary: Usage is read from whichever transcript has the newest mtime rather than the session's own, so runs are billed against unrelated files and only 33 of 1006 carry usage at all.
- Keywords: transcript resolution, conversation id, session-id, mtime race, scan deadline, usage coverage
- Use when: Changing how a session's provider transcript is located for usage reading.
- Skip when: Changing token arithmetic (`item_126`) or per-run delta computation (`item_127`).

# Problem
- `_latest_transcript` walks the whole provider data root and returns the `.jsonl` with the newest mtime after the run started, regardless of which session wrote it. Any concurrent session, or any unrelated file the provider touched, wins the race.
- The walk is bounded by a one-second deadline and a 1000-candidate cap, both of which return an arbitrary partial result rather than reporting that the scan was inconclusive.
- The consequences are visible in the table: sessions reporting several runs with usage totalling 8, 12, or 18 output tokens, and only 33 of 1006 runs carrying usage at all.
- cdx already knows the identity it needs: it passes `--session-id` to Claude (`src/provider_runtime.py:555`) and observes Codex's conversation id back after each run, so the correct transcript is addressable directly.
- The resolution is already implemented. `find_session_transcript` (`src/provider_background.py:193`) locates `<session_id>.jsonl` under the provider auth home and is used by the native background path; the interactive reader just never calls it. So cdx currently locates the same file by two different rules, one correct and one a race, and this slice is a reuse rather than a new algorithm.

# Scope
- In:
  - Resolve the transcript from the session's recorded conversation id, reusing `find_session_transcript` rather than writing a second resolver, and extending it to Codex's rollout naming instead of ranking files by mtime.
  - Keep a narrowly-scoped fallback for sessions with no recorded conversation id, and make it distinguishable from a confident match so a wrong attribution cannot masquerade as a measurement.
  - Report an inconclusive scan as absence rather than returning whichever candidate was found before the deadline.
  - Preserve the existing guarantee that missing or unreadable usage never fails a launch.
  - Verify the coverage improvement against real launch history rather than assuming it, and state the before and after share of runs carrying usage.
  - Add tests with several transcripts present, including one written more recently by a different session, asserting the session's own transcript is the one measured.
- Out:
  - No change to how conversation ids are minted or observed.
  - No new provider integrations.
  - No change to the token arithmetic or to delta computation.

# Acceptance criteria
- Given several transcripts under the provider root, one of them written more recently by a different session, usage is read from the transcript matching the session's own conversation id.
- Given a session with a recorded conversation id whose transcript does not exist, usage is reported absent and the launch outcome is unchanged.
- Given a session with no recorded conversation id, the fallback result is marked as unconfirmed rather than presented identically to an id-matched read.
- Given a provider root large enough to exhaust the scan deadline, the result is absence rather than an arbitrary partial candidate.
- Given a normal interactive run, a test asserts the recorded usage is non-empty and matches the transcript's content, not merely that no exception was raised.
- The share of runs carrying usage measured against real launch history is reported before and after, and the after value is materially higher.
- Only one transcript resolver remains in the codebase; the interactive and native-background paths locate a session's transcript by the same rule.

# AC Traceability
- request-AC4 -> This backlog slice. Proof: Given several transcripts under the provider root, one of them written more recently by a different session, usage is read from the transcript matching the session's own conversation id.
- request-AC5 -> This backlog slice. Proof: Given a session with a recorded conversation id whose transcript does not exist, usage is reported absent and the launch outcome is unchanged.
- request-AC8 -> This backlog slice. Proof: Given a session with no recorded conversation id, the fallback result is marked as unconfirmed rather than presented identically to an id-matched read.

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

# Tasks
- `task_073_orchestrate_truthful_token_accounting_for_cdx_stats`

# Notes
- Task `task_073_orchestrate_truthful_token_accounting_for_cdx_stats` was finished via `logics-manager flow finish task` on 2026-08-14.
