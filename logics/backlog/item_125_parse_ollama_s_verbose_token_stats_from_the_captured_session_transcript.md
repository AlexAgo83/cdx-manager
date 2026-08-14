## item_125_parse_ollama_s_verbose_token_stats_from_the_captured_session_transcript - Parse ollama's verbose token stats from the captured session transcript
> From version: 0.19.3
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Usage tracking
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-14 12:10:50

# AI Context
- Summary: Turn on ollama's `--verbose`, normalize the PTY capture, and parse the token counts out of it — a fourth reader plugged into the field definition req_063_make_cdx_stats_report_the_tokens_a_session_actually_spent settles first.
- Keywords: ollama, --verbose, prompt eval count, PTY normalization, _normalize_terminal_transcript, provider flag health check
- Use when: Implementing ollama token extraction.
- Skip when: req_063_make_cdx_stats_report_the_tokens_a_session_actually_spent has not landed yet — this slice adopts its shared definition rather than predating it.

# Problem
- `cdx` launches ollama without `--verbose`, so no token-count output exists anywhere to capture.
- Even with `--verbose` on, `interactive_usage.extract_interactive_usage` has no ollama branch and its `_latest_transcript` helper only knows how to walk codex's and claude's provider-native transcript directories, neither of which ollama has.
- The transcript is a PTY capture: an ollama spinner frame carries OSC and cursor-control sequences, and carriage returns overwrite lines in place. A regex against those raw bytes will miss, and the fix is not a new cleaner — `_normalize_terminal_transcript` (`src/status_source.py:44`) already does exactly this and is already applied to PTY captures at `src/cli_helpers.py:343`.
- cdx would start passing a launch flag that nothing verifies. `_provider_flag_issues` (`src/health.py:225`) exists because `--experimental-yolo` was once mapped for ollama and that CLI never had it, but it checks only permission mappings — a launch flag slips straight past, and `test/test_provider_flags_py.py:86` currently asserts that ollama maps nothing at all.

# Scope
- In:
  - Add `--verbose` to the ollama launch args in `_build_launch_spec`, as `["run", model, "--verbose"] + config_args + [prompt]`. The placement is settled: ollama 0.32.11 accepts `--verbose` between model and prompt, parsing the arguments and failing only on the model pull.
  - Add an `_ollama_usage` parser in `interactive_usage.py` alongside `_codex_usage`/`_claude_usage`, matching the `prompt eval count` / `eval count` lines from ollama's verbose stats block into `input_tokens`/`output_tokens`, with `total_tokens` as their sum and `cached_input_tokens`/`reasoning_tokens` left `None`.
  - Normalize the captured transcript with `_normalize_terminal_transcript` before matching, importing it from `src/status_source.py` rather than reimplementing the cleanup. That module imports only `config`, so there is no cycle.
  - Confirm the exact text layout of the stats block against a real `ollama run <model> --verbose` invocation before finalizing the regex — the one genuinely unverified assumption left, since `--verbose` is documented as showing timings and the token counts ride inside that block. Capture the real output as the fixture rather than authoring a guessed one.
  - Extend `_provider_flag_issues` (`src/health.py:225`) to cover launch flags, not only permission mappings, so the flag cdx now passes is verified against the provider CLI's own help. It already spawns that help; only the set of flags it checks is missing. Update `test/test_provider_flags_py.py`, whose current ollama case asserts that nothing is mapped.
  - Thread the cdx-generated terminal transcript path into the ollama usage lookup, since ollama has no provider-native transcript directory to walk — extend `extract_interactive_usage`'s inputs (or the call site in `src/commands/launch.py:299-306`) with the already-available `run_info["transcript_path"]` for this provider only, leaving the codex/claude directory-walk path untouched.
  - Fail soft to `empty_usage()` on any parse miss (missing flag output, changed format, truncated transcript), never raising.
  - Tests: a representative captured-transcript fixture with a verbose stats block asserting correct token extraction; a fixture without the block asserting empty usage; a regression test confirming claude/codex extraction is unaffected.
  - Record, in a comment near the ollama parser or in the README's usage-tracking notes, that antigravity token usage was investigated and found not retrievable (schema-less binary protobuf transcripts, no usage-bearing CLI log output), so it is a documented dead end rather than an oversight.
- Out:
  - No antigravity usage parsing.
  - No change to `run_usage.SUPPORTED_PROVIDERS`. Opening the gate without a text parser changes no behavior — `_parse_json_records` reads only JSON — while making the gate claim a support it cannot deliver. It stays closed until something actually runs ollama headless.
  - No renegotiation of the shared field definition or the transcript-resolution rule settled by the preceding request; this slice adopts both.
  - No change to how the codex/claude directory-walk transcript discovery works.
  - No retroactive re-parsing of previously captured ollama transcripts that predate `--verbose`.

# Acceptance criteria
- Given an ollama session launched after this change, its captured transcript contains a verbose stats block.
- Given a captured transcript containing that block, `extract_interactive_usage("ollama", ...)` returns non-`None` `input_tokens`, `output_tokens`, and `total_tokens`.
- Given a transcript whose stats block is interleaved with escape sequences and carriage-return overwrites as a real PTY capture is, extraction still succeeds, and the normalization comes from the existing shared helper rather than a second implementation.
- Given a captured transcript without the block (or with an unrecognized format), `extract_interactive_usage("ollama", ...)` returns `empty_usage()` and does not raise.
- Given the same inputs as before this change, `extract_interactive_usage("claude", ...)` and `extract_interactive_usage("codex", ...)` return identical results to before.
- Given a launch flag cdx passes that the provider CLI does not accept, the provider-flag health check reports it instead of staying silent.
- A test exercises `cdx stats`-equivalent aggregation and shows a non-zero total for a fixture ollama session.
- The antigravity dead end is recorded in the code or README near the usage-extraction path, not only in this corpus.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: Given an ollama session launched after this change, its captured transcript contains a verbose stats block.
- request-AC2 -> This backlog slice. Proof: Given a captured transcript containing that block, `extract_interactive_usage("ollama", ...)` returns non-`None` `input_tokens`, `output_tokens`, and `total_tokens`.
- request-AC3 -> This backlog slice. Proof: Given a transcript whose stats block is interleaved with escape sequences and carriage-return overwrites as a real PTY capture is, extraction still succeeds, and the normalization comes from the existing shared helper rather than a second implementation.
- request-AC4 -> This backlog slice. Proof: Given a captured transcript without the block (or with an unrecognized format), `extract_interactive_usage("ollama", ...)` returns `empty_usage()` and does not raise.
- request-AC5 -> This backlog slice. Proof: A test exercises `cdx stats`-equivalent aggregation and shows a non-zero total for a fixture ollama session.
- request-AC6 -> This backlog slice. Proof: Given the same inputs as before this change, `extract_interactive_usage("claude", ...)` and `extract_interactive_usage("codex", ...)` return identical results to before.
- request-AC7 -> This backlog slice. Proof: Given a launch flag cdx passes that the provider CLI does not accept, the provider-flag health check reports it instead of staying silent.
- request-AC8 -> This backlog slice. Proof: The antigravity dead end is recorded in the code or README near the usage-extraction path, not only in this corpus.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_048_ollama_sessions_report_real_token_usage`
- Architecture decision(s): (none yet)
- Blocked on: `req_063_make_cdx_stats_report_the_tokens_a_session_actually_spent`
- Request: `req_062_track_token_usage_for_interactive_ollama_sessions`
- Primary task(s): `task_072_orchestrate_ollama_token_usage_tracking`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
