## task_072_orchestrate_ollama_token_usage_tracking - Orchestrate ollama token usage tracking
> From version: 0.19.3
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 95%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-14 12:41:27
> Owner: claude

# AI Context
- Summary: Sequenced after the token-accounting request; the only real unknown left is the text layout of ollama's verbose stats block, so that is captured first and everything else follows from a real fixture.
- Keywords: ollama, --verbose, PTY normalization, provider flag health check, sequencing
- Use when: Implementing or sequencing req_062_track_token_usage_for_interactive_ollama_sessions.
- Skip when: the token-accounting request is still open — this work adopts its shared definition and must not predate it.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.
- **Blocked on the token-accounting request (`cdx stats` truthful accounting).** That request settles the shared usage-field definition, what a run stores, and how a transcript is resolved. Starting here first means writing a fourth reader against three divergent ones, and its single-resolver outcome would contradict ollama's separate source on arrival. Confirm that request's orchestration task is closed out before starting step 2.

# Plan
- [x] 1. Confirm the token-accounting request has landed and read the shared field definition it settled. Everything below plugs into that definition rather than proposing another.
- [x] 2. Capture ollama's real `--verbose` stats block from a live run and keep the raw output — escapes included — as the test fixture. This is the only genuinely unverified assumption in the request: the flag's placement is already settled, and `--verbose` is documented as showing timings, so whether and how the token counts appear inside that block is what the live run answers. Do not author a guessed fixture.
- [x] 3. Add `--verbose` to the ollama launch args as `["run", model, "--verbose"] + config_args + [prompt]`, and confirm prompt, model, and existing extra-arg handling are unaffected.
- [x] 4. Add the `_ollama_usage` parser to `interactive_usage.py`, wired through the cdx-generated transcript path for ollama specifically, leaving the resolution path settled by the preceding request untouched for the other providers.
- [x] 5. Normalize before matching: import `_normalize_terminal_transcript` from `src/status_source.py` rather than writing a second cleanup. Verify the parser against the raw fixture from step 2, not a hand-cleaned copy of it — a parser that only works on cleaned text is one that fails in production.
- [x] 6. Extend `_provider_flag_issues` to cover launch flags, and update the ollama case in `test/test_provider_flags_py.py`, which currently asserts nothing is mapped. Do this in the same pass as step 3: it is the flag added there that creates the unverified surface.
- [x] 7. Write fixture-based tests: verbose block present, block absent or malformed, and a claude/codex regression check.
- [x] 8. Manually verify `cdx stats`/`cdx history` show non-zero ollama tokens after one real launch.
- [x] 9. Record the antigravity dead-end explicitly in code comments or README near the usage-extraction code, not just in this corpus, so a future contributor doesn't re-attempt it without reading this task.
- [x] 10. Run the full test suite, then `logics-manager lint --require-status` and `logics-manager audit --group-by-doc` before closeout.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_125_parse_ollama_s_verbose_token_stats_from_the_captured_session_transcript`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: `--verbose` is passed via LAUNCH_FEATURE_ARGS; `test_ollama_permission_maps_to_nothing_but_keeps_the_usage_flag` and `test_build_launch_spec_supports_ollama`. 0dfa9ca
- request-AC2 -> This task. Proof: `extract_interactive_usage('ollama', ...)` reads the run's own PTY capture; `OllamaResolutionTests.test_the_runs_own_capture_is_the_source`. b5bfb64
- request-AC3 -> This task. Proof: Parsed after `_normalize_terminal_transcript`, asserted against the raw capture; `test_escape_sequences_do_not_defeat_the_match`. b5bfb64
- request-AC4 -> This task. Proof: A missing or changed block returns absence and never raises; `test_a_capture_without_the_block_is_absence_not_an_error`, `test_a_changed_format_degrades_to_absence`. b5bfb64
- request-AC5 -> This task. Proof: `cdx stats` shows non-zero ollama tokens after a real interactive launch -- IN 34 / OUT 76 / TOTAL 110, operator-verified 2026-08-14 -- and `test_the_real_capture_yields_its_token_counts` pins the parser against a real capture. b5bfb64
- request-AC6 -> This task. Proof: Claude and Codex extraction is untouched and the shared definition is adopted, not renegotiated; the full suite passes at 942 with the claude/codex usage tests unchanged. b5bfb64
- request-AC7 -> This task. Proof: The provider-flag health check now covers cdx's own launch flags; `test_a_cdx_feature_flag_the_cli_lacks_is_reported`. 0dfa9ca
- request-AC8 -> This task. Proof: The antigravity dead end is recorded in `src/interactive_usage.py`'s module docstring and in the README. b5bfb64

# Validation
- 2026-08-14: `npm test` 942 passed, `npm run lint` all checks passed. Baseline before this task was 935.
- End-to-end verified by the operator through a real interactive launch: `cdx stats` reports `olla ollama 13 runs / 1 usage / IN 34 / OUT 76 / TOTAL 110 / COST~ 414 / USD~ -`.
- Format confirmed against a real run rather than assumed: `script -q -F log ollama run smollm2:135m --verbose "say hi"` on ollama 0.32.11. The captured block reads `prompt eval count: 32 token(s)` / `eval count: 58 token(s)`, and the raw capture — cursor sequences and carriage returns included — is the test fixture. The model was pulled for this and removed afterwards.
- Flag placement confirmed earlier against the same version: `ollama run MODEL [PROMPT] [flags]` accepts `--verbose` between model and prompt.
- command: `npm test && npm run lint` | result: passed | date: 2026-08-14
- Finish workflow executed on 2026-08-14.
- Linked backlog/request close verification passed.

# Report
- **Delivered** in 0dfa9ca and b5bfb64, after the token-accounting request landed and its shared field definition existed to adopt.
- `--verbose` now arrives through `LAUNCH_FEATURE_ARGS`, so the launch spec and the provider-flag health check read one table. That check previously covered permission mappings only: issue #8 was a mapped flag the CLI never had, and a flag cdx invents for a feature of its own is exactly as capable of not existing. It now verifies both.
- The parser normalizes the PTY capture with `_normalize_terminal_transcript` before matching, reusing the helper the handoff reader already applies rather than writing a second cleanup. The test asserts against the **raw** capture, escapes included — a parser that only works on cleaned text is one that fails in production.
- Each response contributes one `--verbose` block and they sum. No delta handling is needed: cdx writes one transcript per launch (`cdx-session-<timestamp>-<pid>.log`), so nothing accumulates across runs.
- Ollama reports no cache and no reasoning, and its usage record carries no model: local models are in no price table, and naming one would invite pricing something that is free. The `USD~` column stays empty for these sessions by nature.
- The antigravity dead end is recorded in `src/interactive_usage.py`'s module docstring and in the README, not only in this corpus.
- **Step 8 verified by the operator on 2026-08-14.** A real interactive launch of the `olla` session (smollm2:135m) through the working tree recorded `IN 34 / OUT 76 / TOTAL 110`, `COST~ 414`, with `provider_transcript_match: run_transcript` and the run's own capture named on the entry. `CACHE` and `REASON` are 0 because ollama has neither, and `USD~` is empty because a local model is in no price table — each column saying what it should.
- A first attempt measured nothing, and the reason is worth recording: `cdx` on PATH resolves to the installed release at `~/.local/share/cdx-manager/0.19.3/`, a separate copy of the tree. That run exercised the released binary, whose transcript contained no `eval count` at all. The parser returned absence on it rather than failing, which is the contract holding on a real file. Verifying unreleased behaviour means running `node <repo>/bin/cdx.js`, not `cdx`.
- **Out of scope, not started:** `run_usage.SUPPORTED_PROVIDERS` still excludes ollama, deliberately. Opening that gate without a text parser would change no behaviour while making the gate claim a support it cannot deliver.
- Finished on 2026-08-14.
- Linked backlog item(s): `item_125_parse_ollama_s_verbose_token_stats_from_the_captured_session_transcript`
- Related request(s): `req_062_track_token_usage_for_interactive_ollama_sessions`

# Links
- Request: `req_062_track_token_usage_for_interactive_ollama_sessions`
- Product brief(s): `prod_048_ollama_sessions_report_real_token_usage`
- Architecture decision(s): (none yet)
