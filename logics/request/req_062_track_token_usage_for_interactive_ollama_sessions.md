## req_062_track_token_usage_for_interactive_ollama_sessions - Track token usage for interactive ollama sessions
> From version: 0.19.3
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Usage tracking
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: track, token, usage, interactive, ollama, sessions
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Needs
- `cdx stats` and `cdx history` report token usage for `claude` and `codex` sessions but always show zero for `ollama` sessions, even after real runs, because ollama is absent from both usage-extraction paths.
- `src/run_usage.py:4` hardcodes `SUPPORTED_PROVIDERS = {"claude", "codex"}`, so `extract_run_usage` (`src/run_usage.py:11`) returns `empty_usage()` unconditionally for `ollama` regardless of what the run actually produced.
- `src/interactive_usage.py:11`'s `extract_interactive_usage`, which is what actually feeds `cdx history`/`cdx stats` for interactive launches (called from `_attach_interactive_usage` in `src/commands/launch.py:299`), only branches on `codex` vs. everything-else-treated-as-`claude` (`src/interactive_usage.py:19`) and its `_latest_transcript` helper (`src/interactive_usage.py:29`) only knows the `codex` `sessions/` directory and the claude `.claude/projects/` directory under `auth_home` — there is no ollama case at all.
- Ollama has no provider-native transcript directory under `auth_home` the way codex and claude do: `src/provider_runtime.py:591-606` launches it as a plain `ollama run <model>` with no `HOME`/config-dir override, so there is nothing under `auth_home` to scan for a fixed-format transcript.
- Ollama's CLI does support a `--verbose` flag that prints a token-count stats block (prompt eval count, eval count) to the terminal after each response, but cdx does not currently pass that flag, and that output only ever lands in the generic terminal transcript that `_wrap_launch_with_transcript` (`src/provider_runtime.py:475`) already tees to `run_info["transcript_path"]` for every provider — not in an ollama-native log file.
- A prior investigation this session also looked at extracting usage for the `antigravity` provider and found no viable source: its conversation history is stored in schema-less binary protobuf files (`~/.gemini/antigravity-cli/conversations/*.pb`) with no `.proto` definitions available to decode field numbers into token counts, and its CLI log files are plain glog output with no usage-bearing log line at any verbosity level exposed by `agy --help`. That path is a dead end for now and is explicitly out of scope for this request.

# Context
- Two independent usage-extraction paths exist today: `run_usage.extract_run_usage` for detached/non-interactive `cdx run` (reads `stdout_path`, used by `src/run_command.py:186`), and `interactive_usage.extract_interactive_usage` for interactive terminal launches (reads a provider-native transcript directory under `auth_home`, used by `src/commands/launch.py:299`). The `cdx history`/`cdx stats` rows in question come from interactive launches, so `interactive_usage.py` is the path that must change; `run_usage.py`'s `SUPPORTED_PROVIDERS` gate should still be extended for parity so a future non-interactive ollama run is not silently dropped either.
- `interactive_usage.py`'s existing parsers (`_codex_usage` at line 68, `_claude_usage` at line 83) read a provider-native JSON/JSONL transcript file discovered by walking a fixed directory. Ollama has no such directory, so an ollama parser cannot reuse `_latest_transcript`'s directory-walk unmodified — it needs the cdx-generated terminal transcript path instead (already computed by the caller and available as `run_info.get("transcript_path")` in `src/commands/launch.py:301-304`, but not currently passed into `extract_interactive_usage`).
- `extract_interactive_usage`'s docstring already states the operating philosophy to keep: "Provider transcripts are not stable public APIs. A missing or changed record is therefore ordinary absence, never a launch failure." The ollama parser must fail soft (return no usage) if `--verbose`'s text format doesn't match, rather than raising.
- The exact text layout of ollama's `--verbose` stats block (e.g. `prompt eval count: N token(s)`, `eval count: N token(s)`) has not been confirmed against a live run on the machine this was scoped from (no local model was pulled), so the parser's regex needs to be validated against real `ollama run <model> --verbose` output early in implementation, using whatever model is available in the dev/CI environment.
- Ollama does not report cached-input or reasoning tokens, so `cached_input_tokens` and `reasoning_tokens` stay `None` for ollama the same way `empty_usage()` already models absence for other providers; `total_tokens` can be derived as the sum of prompt and eval counts when both are present.
- `ponytail` mode is active for this codebase: reuse the existing usage-extraction shape (a small per-provider parser function plus one dispatch point) rather than introducing a new abstraction layer for provider usage sources.

# Acceptance criteria
- AC1: `ollama` is added to `run_usage.SUPPORTED_PROVIDERS` so a non-interactive ollama run's usage is no longer unconditionally suppressed.
- AC2: cdx passes `--verbose` when launching an interactive ollama session, without changing ollama's launch behavior for the user (model, prompt, and other existing args are unaffected).
- AC3: `interactive_usage.extract_interactive_usage` returns non-empty `input_tokens`/`output_tokens`/`total_tokens` for an ollama session whose captured transcript contains a `--verbose` stats block, sourced from the cdx-generated terminal transcript (not a provider-native directory scan, since none exists for ollama).
- AC4: A malformed, missing, or format-changed ollama verbose block results in `empty_usage()`-shaped absence, not an exception, consistent with the existing best-effort contract documented on `extract_interactive_usage`.
- AC5: `cdx stats` and `cdx history` show non-zero token totals for an ollama session after a real interactive run with `--verbose` output present, verified by a test with a representative captured transcript fixture.
- AC6: Existing `claude` and `codex` usage extraction behavior is unchanged; the ollama branch is additive.
- AC7: The decision that `antigravity` token usage is not currently retrievable (schema-less binary protobuf transcripts, no usage-bearing log output) is recorded as an explicit non-goal, so it is not silently reattempted or mistaken for an oversight.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_048_ollama_sessions_report_real_token_usage`
- Architecture decision(s): (none yet)

# References
- src/interactive_usage.py
- src/provider_runtime.py
- src/run_usage.py
- src/commands/launch.py
- src/config.py
- test/test_interactive_usage_py.py
- test/test_run_usage_py.py
- test/test_provider_runtime_helpers_py.py

# Backlog
- `item_125_parse_ollama_s_verbose_token_stats_from_the_captured_session_transcript`
