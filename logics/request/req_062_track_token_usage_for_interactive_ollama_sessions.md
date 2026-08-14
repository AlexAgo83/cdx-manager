## req_062_track_token_usage_for_interactive_ollama_sessions - Track token usage for interactive ollama sessions
> From version: 0.19.3
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Usage tracking
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-14 12:41:27

# AI Context
- Summary: Ollama has no provider-native transcript, so its token counts have to come from `--verbose` output parsed out of the PTY capture cdx already takes — which means normalizing terminal escapes before any regex runs.
- Keywords: ollama, --verbose, prompt eval count, terminal transcript, PTY capture, interactive_usage, antigravity dead end
- Use when: Adding or changing token-usage extraction for ollama.
- Skip when: Working on claude or codex usage — that is the token-accounting request, and it lands first.

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
- **This request follows the token-accounting request and must not land before it.** That request rewrites the same surfaces: it settles one shared field definition across every usage reader, changes what a run stores, and replaces the transcript-discovery rule. Adding a provider to that surface first means writing against a shape that is about to change, and its outcome of a single transcript resolver would immediately contradict ollama's separate source. Sequencing it second also makes this request cheaper — ollama plugs into a definition that already exists rather than negotiating with three divergent readers.
- The terminal transcript is a PTY capture taken through `script`, not clean text. A single spinner frame from a real ollama invocation carries OSC and cursor-control sequences, and carriage returns overwrite lines in place. A regex run against those bytes is unreliable — but the normalizer already exists: `_normalize_terminal_transcript` (`src/status_source.py:44`) strips OSC sequences, terminal control, escapes and control characters, and turns carriage returns into newlines. It is already applied to exactly this kind of capture (`src/cli_helpers.py:343`), and `status_source` imports only `config`, so reusing it from `interactive_usage` creates no import cycle.
- Flag placement is settled and needs no live check: `ollama run MODEL [PROMPT] [flags]` accepts `--verbose` between the model and the prompt — verified against ollama 0.32.11, which parsed the arguments and failed only on the model pull. What genuinely remains unverified is the **text layout** of the stats block, since `--verbose` is documented as "Show timings for response" and the token counts ride inside that block.
- The non-interactive path is deliberately left alone. Adding `ollama` to `run_usage.SUPPORTED_PROVIDERS` without a text parser would change nothing — `_parse_json_records` reads only JSON, so `extract_run_usage` would still return `empty_usage()`, just by a different branch — while making the gate claim a support the parser cannot deliver. Nothing runs ollama headless through cdx today, so the honest move is to leave the gate closed and record why.

# Acceptance criteria
- AC1: cdx passes `--verbose` when launching an interactive ollama session, without changing ollama's launch behavior for the user (model, prompt, and other existing args are unaffected).
- AC2: `interactive_usage.extract_interactive_usage` returns non-empty `input_tokens`/`output_tokens`/`total_tokens` for an ollama session whose captured transcript contains a `--verbose` stats block, sourced from the cdx-generated terminal transcript (not a provider-native directory scan, since none exists for ollama).
- AC3: The stats block is parsed after terminal normalization, so escape sequences and carriage-return overwrites in the PTY capture do not defeat extraction, and the existing normalizer is reused rather than reimplemented.
- AC4: A malformed, missing, or format-changed ollama verbose block results in `empty_usage()`-shaped absence, not an exception, consistent with the existing best-effort contract documented on `extract_interactive_usage`.
- AC5: `cdx stats` and `cdx history` show non-zero token totals for an ollama session after a real interactive run with `--verbose` output present, verified by a test with a representative captured transcript fixture.
- AC6: Existing `claude` and `codex` usage extraction behavior is unchanged; the ollama branch is additive, and the shared field definition settled by the token-accounting request is not renegotiated.
- AC7: The launch flag cdx adds is covered by the provider-flag health check, so a flag cdx passes that the provider CLI does not accept is reported rather than discovered by a user — the generalized form of the gap that check was built for.
- AC8: The decision that `antigravity` token usage is not currently retrievable (schema-less binary protobuf transcripts, no usage-bearing log output) is recorded as an explicit non-goal, so it is not silently reattempted or mistaken for an oversight.

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
- src/status_source.py
- src/health.py
- test/test_provider_flags_py.py
- test/test_interactive_usage_py.py
- test/test_run_usage_py.py
- test/test_provider_runtime_helpers_py.py

# Backlog
- `item_125_parse_ollama_s_verbose_token_stats_from_the_captured_session_transcript`
