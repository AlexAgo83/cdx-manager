## req_063_make_cdx_stats_report_the_tokens_a_session_actually_spent - Make cdx stats report the tokens a session actually spent
> From version: 0.19.3
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: High
> Theme: Usage accounting
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-14 10:19:17

# AI Context
- Summary: The interactive usage reader drops cached input from the total, re-bills the whole transcript on every resume, and often measures a different session's transcript entirely.
- Keywords: cdx stats, token usage, cache_read_input_tokens, interactive_usage, run_usage, launch history, transcript
- Use when: Changing how token usage is read, normalized, stored per run, or displayed by `cdx stats`.
- Skip when: Working on rate limits, credits, or quota display — those come from provider APIs, not transcripts.

# Needs
- `cdx stats` is the only place cdx reports what a session cost, and every number in its table is wrong for Claude sessions in a different way. A user reading it draws conclusions about spend and session ranking from figures that do not correspond to any real consumption.
- The TOTAL column excludes cached input entirely. `_claude_usage` (`src/interactive_usage.py:104`) computes `total_tokens = input_tokens + output_tokens`, but for Claude `input_tokens` counts only the *uncached* prompt; the bulk of the volume sits in `cache_creation_input_tokens` and `cache_read_input_tokens`. An observed session reported IN 1.7M, CACHE 7.6M, TOTAL 1.8M — the TOTAL omits roughly 80% of what was consumed.
- That same wrong TOTAL is the sort key of the stats table (`_summarize_stats`, `src/commands/status.py:286`), so the ordering of sessions by cost is wrong too, and a cache-heavy session ranks below a session that spent a fraction as much.
- Usage is double-counted across runs. `_claude_usage` sums the *entire* transcript file on every launch, `_attach_interactive_usage` (`src/commands/launch.py:299`) stores that whole-file cumulative as the run's usage, and `_summarize_stats` then sums it again across runs. Two consecutive `cdx stats` calls separated by a single launch showed CACHE going 2.6M to 7.6M and OUT 44.0K to 88.9K while RUNS went 71 to 72. A resumed session re-bills its full history on every resume.
- The transcript being measured is frequently not the session's own. `_latest_transcript` (`src/interactive_usage.py:29`) walks all of `~/.claude/projects` and returns whichever `.jsonl` has the newest mtime after the run started, under a one-second scan deadline. The symptom is visible in the table: sessions reporting three runs with usage and a total of 8, 12, or 18 output tokens — a match against a near-empty unrelated file. Across the observed history only 33 of 1006 runs carry any usage at all.
- The IN column means two different things depending on the provider. Codex's `total_token_usage.input_tokens` already includes cached input; Claude's does not. The two are printed in the same column with no distinction, so no cross-provider comparison read from that table is valid.
- It means two different things within Claude alone, because there is a third reader. `read_transcript_outcome` (`src/provider_background.py:213`) closes out native background runs with its own arithmetic: it folds the cache fields into `input_tokens`, emits no `cached_input_tokens` key at all, and therefore produces a total that *is* cache-inclusive — the exact inverse of `_claude_usage`. Two runs of the same Claude session, one interactive and one detached, feed the same TOTAL column under opposite definitions, and the detached one leaves CACHE structurally empty.
- The README already states the invariant the code violates. `README.md:711` promises that "cached input is retained separately from the provider's total, so it is never counted twice", which is precisely what `run_usage._usage_from_dict` does not honor. `README.md:540` still describes `cdx stats` as aggregating only headless token usage, which stopped being true when interactive recording landed.

# Context
- There are three independent usage readers, not two. `src/run_usage.py` parses provider stdout for headless runs, `src/interactive_usage.py` reads provider transcripts after interactive runs, and `src/provider_background.py` reads them again when a native background run closes out. They disagree on the same questions: `_usage_from_dict` (`src/run_usage.py:80`) folds `cache_creation_input_tokens` and `cache_read_input_tokens` *into* `input_tokens` and also reports them as `cached_input_tokens`, double-counting the cache within one record; `_claude_usage` keeps the two disjoint and drops the cache from the total; `read_transcript_outcome` folds them in and omits the cached field entirely. All three write into the same launch history and the same stats table.
- The usage record is a published contract, not only a table cell. `run_result_payload` (`src/run_command.py:212`) puts it in `cdx run --json`, and `cdx run-status` and `cdx run-report` surface it from the registry (`src/commands/runs.py:483`, `:492`). `README.md:709` describes these as "normalized usage token fields". Redefining the fields changes a programmatic surface, so the definition has to be stated and versioned rather than adjusted in place.
- `src/run_registry.py:194` seeds `usage: None` on every run record and `:318` overwrites it from the closing payload verbatim. It does not normalize, so whichever shape the producing reader emitted — including `provider_background`'s missing `cached_input_tokens` — propagates into the registry and out through the JSON surfaces.
- `_extract_usage_from_records` (`src/run_usage.py:56`) keeps the last record carrying usage rather than summing, which is right for a cumulative `result` record and wrong for per-message records. That assumption is undocumented and untested against a stream where both shapes appear.
- `_summarize_stats` sums whatever each run recorded. It is correct only if each run's stored usage is that run's own increment. Fixing the arithmetic in the readers without fixing what a run *stores* leaves the double counting intact.
- The transcript guess is avoidable. cdx already mints Claude's session id itself and passes it as `--session-id` (`src/provider_runtime.py:555`), and observes Codex's conversation id back after a run (`_observe_codex_conversation`, `src/session_service.py:694`). Claude writes its transcript to `<session-id>.jsonl`, so the session's own transcript is addressable by name rather than by mtime race.
- That resolution is already written and working. `find_session_transcript` (`src/provider_background.py:193`) walks the provider auth home's per-project transcript directories looking for `<session_id>.jsonl` and is used by the native background path. The interactive reader simply does not call it. The correction is to reuse an existing function, not to author a new one — which also means the two paths currently locate the same file by two different rules.
- `_attach_interactive_usage` already records `provider_transcript_path` into the run entry (`src/commands/launch.py:308`), and nothing ever reads it back. It is the natural anchor for computing a per-run delta against the previous run on the same transcript.
- Absence of usage must stay non-fatal. The docstring on `extract_interactive_usage` is explicit that transcripts are not a stable public API and that a missing record is ordinary absence, never a launch failure. Every change here keeps that property — a stricter reader that starts failing launches is a worse outcome than a wrong number.
- The USAGE column already counts how many runs carried usage, so the table has a built-in coverage signal. 33/1006 is the measurement of the problem, and the same column is the measurement of the fix.
- An independent oracle exists for verification. The external ccusage tool reads the same Claude transcripts and reports input, cache-creation, cache-read, and output separately, and because cdx isolates each session by setting `HOME` to its auth home (`_home_env_overrides`, `src/provider_runtime.py:124`), running it as HOME=<auth_home> npx ccusage --json scopes it to exactly one cdx session. Measured against the whole machine it reports roughly 4.44 billion tokens where `cdx stats` reports 5.5 million — a gap of about 800x, of which cache reads alone are 99%. This is a check to compare against during development, not a dependency to take: it is a Node tool fetched over the network, and cdx is a Python CLI that must keep reporting usage offline.

# Acceptance criteria
- AC1: The TOTAL reported for a Claude session accounts for cached input. A session whose transcript shows uncached input, cache creation, cache reads, and output reports a total covering all of them, not just the uncached input plus output.
- AC2: The stats table is ordered by that corrected total, so the session that consumed the most tokens appears first.
- AC3: A run records only the tokens spent during that run. Launching a session twice against a transcript that grew by a known amount produces a second run entry carrying that increment, not the transcript's running total, and `cdx stats` for the two runs sums to the transcript's total rather than to a multiple of it.
- AC4: Usage is read from the transcript belonging to the session that ran, resolved from the conversation id cdx already assigns, not from whichever file in the provider's data directory was touched most recently.
- AC5: When the session's own transcript cannot be resolved or read, usage is reported as absent rather than attributed from another session's file, and the launch still succeeds unchanged.
- AC6: The IN column means the same thing for every provider — either cache-inclusive everywhere or cache-exclusive everywhere — and the README states which, so a reader can compare a Claude row against a Codex row.
- AC7: All three readers — headless (`src/run_usage.py`), interactive (`src/interactive_usage.py`), and native background (`src/provider_background.py`) — produce the same field semantics for the same underlying consumption, so a session's stats do not shift meaning depending on how it was launched. Every usage record carries the full field set, including `cached_input_tokens`.
- AC8: The share of runs carrying usage, visible in the USAGE column, is materially higher than today's 33 of 1006 for sessions that actually produced a transcript, and a test asserts usage is captured for a normal interactive run rather than only that the code path does not crash.
- AC9: The usage fields published by `cdx run --json`, `cdx run-status --json`, and `cdx run-report --json` carry the same definition as the stats table, and the run registry stores that normalized shape rather than whatever the producing reader happened to emit.
- AC10: The README's claims about token usage are true of the code: the "never counted twice" invariant at `README.md:711` holds or is restated, and the `cdx stats` description no longer limits itself to headless usage.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_049_token_numbers_a_user_can_act_on`
- Architecture decision(s): (none yet)

# References
- src/interactive_usage.py
- src/run_usage.py
- src/commands/status.py
- src/commands/launch.py
- src/session_service.py
- src/provider_runtime.py
- src/provider_background.py
- src/run_command.py
- src/run_registry.py
- src/commands/runs.py
- README.md
- test/test_interactive_usage_py.py
- test/test_commands_status_py.py
- test/test_codex_usage_py.py

# Backlog
- `item_126_define_one_token_accounting_shared_by_both_usage_readers`
- `item_127_bill_each_run_for_its_own_tokens_instead_of_the_whole_transcript`
- `item_128_read_usage_from_the_session_s_own_transcript_not_the_newest_file`
