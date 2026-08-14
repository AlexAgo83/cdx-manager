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

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: parse, ollama, verbose, token, stats, captured, session, transcript
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- `cdx` launches ollama without `--verbose`, so no token-count output exists anywhere to capture.
- Even with `--verbose` on, `interactive_usage.extract_interactive_usage` has no ollama branch and its `_latest_transcript` helper only knows how to walk codex's and claude's provider-native transcript directories, neither of which ollama has.
- `run_usage.SUPPORTED_PROVIDERS` also excludes ollama, so the non-interactive path would suppress its usage too if ever exercised.

# Scope
- In:
  - Add `--verbose` to the ollama launch args in `_build_launch_spec` (`src/provider_runtime.py:591-606`).
  - Add an `_ollama_usage` parser in `interactive_usage.py` alongside `_codex_usage`/`_claude_usage`, matching the `prompt eval count` / `eval count` lines from ollama's verbose stats block into `input_tokens`/`output_tokens`, with `total_tokens` as their sum and `cached_input_tokens`/`reasoning_tokens` left `None`.
  - Confirm the exact text layout against a real `ollama run <model> --verbose` invocation before finalizing the regex; adjust the fixture and parser to match observed output rather than assumed formatting.
  - Thread the cdx-generated terminal transcript path into the ollama usage lookup, since ollama has no provider-native transcript directory to walk — extend `extract_interactive_usage`'s inputs (or the call site in `src/commands/launch.py:299-306`) with the already-available `run_info["transcript_path"]` for this provider only, leaving the codex/claude directory-walk path untouched.
  - Add `ollama` to `run_usage.SUPPORTED_PROVIDERS` (`src/run_usage.py:4`) for parity on the non-interactive path.
  - Fail soft to `empty_usage()` on any parse miss (missing flag output, changed format, truncated transcript), never raising.
  - Tests: a representative captured-transcript fixture with a verbose stats block asserting correct token extraction; a fixture without the block asserting empty usage; a regression test confirming claude/codex extraction is unaffected.
  - Record, in a comment near the ollama parser or in the README's usage-tracking notes, that antigravity token usage was investigated and found not retrievable (schema-less binary protobuf transcripts, no usage-bearing CLI log output), so it is a documented dead end rather than an oversight.
- Out:
  - No antigravity usage parsing.
  - No change to how the codex/claude directory-walk transcript discovery works.
  - No retroactive re-parsing of previously captured ollama transcripts that predate `--verbose`.

# Acceptance criteria
- Given an ollama session launched after this change, its captured transcript contains a verbose stats block.
- Given a captured transcript containing that block, `extract_interactive_usage("ollama", ...)` returns non-`None` `input_tokens`, `output_tokens`, and `total_tokens`.
- Given a captured transcript without the block (or with an unrecognized format), `extract_interactive_usage("ollama", ...)` returns `empty_usage()` and does not raise.
- Given the same inputs as before this change, `extract_interactive_usage("claude", ...)` and `extract_interactive_usage("codex", ...)` return identical results to before.
- `run_usage.extract_run_usage("ollama", stdout_path)` no longer short-circuits to `empty_usage()` solely because of the provider gate.
- A test exercises `cdx stats`-equivalent aggregation and shows a non-zero total for a fixture ollama session.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: Given an ollama session launched after this change, its captured transcript contains a verbose stats block.
- request-AC2 -> This backlog slice. Proof: Given a captured transcript containing that block, `extract_interactive_usage("ollama", ...)` returns non-`None` `input_tokens`, `output_tokens`, and `total_tokens`.
- request-AC3 -> This backlog slice. Proof: Given a captured transcript without the block (or with an unrecognized format), `extract_interactive_usage("ollama", ...)` returns `empty_usage()` and does not raise.
- request-AC4 -> This backlog slice. Proof: Given the same inputs as before this change, `extract_interactive_usage("claude", ...)` and `extract_interactive_usage("codex", ...)` return identical results to before.
- request-AC5 -> This backlog slice. Proof: `run_usage.extract_run_usage("ollama", stdout_path)` no longer short-circuits to `empty_usage()` solely because of the provider gate.
- request-AC6 -> This backlog slice. Proof: A test exercises `cdx stats`-equivalent aggregation and shows a non-zero total for a fixture ollama session.
- request-AC7 -> This backlog slice. Proof: A test exercises `cdx stats`-equivalent aggregation and shows a non-zero total for a fixture ollama session.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_048_ollama_sessions_report_real_token_usage`
- Architecture decision(s): (none yet)
- Request: `req_062_track_token_usage_for_interactive_ollama_sessions`
- Primary task(s): `task_072_orchestrate_ollama_token_usage_tracking`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
