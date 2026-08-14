## task_072_orchestrate_ollama_token_usage_tracking - Orchestrate ollama token usage tracking
> From version: 0.19.3
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-14 12:13:17

# AI Context
- Summary: Sequenced after the token-accounting request; the only real unknown left is the text layout of ollama's verbose stats block, so that is captured first and everything else follows from a real fixture.
- Keywords: ollama, --verbose, PTY normalization, provider flag health check, sequencing
- Use when: Implementing or sequencing req_062_track_token_usage_for_interactive_ollama_sessions.
- Skip when: the token-accounting request is still open — this work adopts its shared definition and must not predate it.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.
- **Blocked on the token-accounting request (`cdx stats` truthful accounting).** That request settles the shared usage-field definition, what a run stores, and how a transcript is resolved. Starting here first means writing a fourth reader against three divergent ones, and its single-resolver outcome would contradict ollama's separate source on arrival. Confirm that request's orchestration task is closed out before starting step 2.

# Plan
- [ ] 1. Confirm the token-accounting request has landed and read the shared field definition it settled. Everything below plugs into that definition rather than proposing another.
- [ ] 2. Capture ollama's real `--verbose` stats block from a live run and keep the raw output — escapes included — as the test fixture. This is the only genuinely unverified assumption in the request: the flag's placement is already settled, and `--verbose` is documented as showing timings, so whether and how the token counts appear inside that block is what the live run answers. Do not author a guessed fixture.
- [ ] 3. Add `--verbose` to the ollama launch args as `["run", model, "--verbose"] + config_args + [prompt]`, and confirm prompt, model, and existing extra-arg handling are unaffected.
- [ ] 4. Add the `_ollama_usage` parser to `interactive_usage.py`, wired through the cdx-generated transcript path for ollama specifically, leaving the resolution path settled by the preceding request untouched for the other providers.
- [ ] 5. Normalize before matching: import `_normalize_terminal_transcript` from `src/status_source.py` rather than writing a second cleanup. Verify the parser against the raw fixture from step 2, not a hand-cleaned copy of it — a parser that only works on cleaned text is one that fails in production.
- [ ] 6. Extend `_provider_flag_issues` to cover launch flags, and update the ollama case in `test/test_provider_flags_py.py`, which currently asserts nothing is mapped. Do this in the same pass as step 3: it is the flag added there that creates the unverified surface.
- [ ] 7. Write fixture-based tests: verbose block present, block absent or malformed, and a claude/codex regression check.
- [ ] 8. Manually verify `cdx stats`/`cdx history` show non-zero ollama tokens after one real launch.
- [ ] 9. Record the antigravity dead-end explicitly in code comments or README near the usage-extraction code, not just in this corpus, so a future contributor doesn't re-attempt it without reading this task.
- [ ] 10. Run the full test suite, then `logics-manager lint --require-status` and `logics-manager audit --group-by-doc` before closeout.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_125_parse_ollama_s_verbose_token_stats_from_the_captured_session_transcript`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_125_parse_ollama_s_verbose_token_stats_from_the_captured_session_transcript`. Proof deferred to slice closeout.
- request-AC2 -> `item_125_parse_ollama_s_verbose_token_stats_from_the_captured_session_transcript`. Proof deferred to slice closeout.
- request-AC3 -> `item_125_parse_ollama_s_verbose_token_stats_from_the_captured_session_transcript`. Proof deferred to slice closeout.
- request-AC4 -> `item_125_parse_ollama_s_verbose_token_stats_from_the_captured_session_transcript`. Proof deferred to slice closeout.
- request-AC5 -> `item_125_parse_ollama_s_verbose_token_stats_from_the_captured_session_transcript`. Proof deferred to slice closeout.
- request-AC6 -> `item_125_parse_ollama_s_verbose_token_stats_from_the_captured_session_transcript`. Proof deferred to slice closeout.
- request-AC7 -> `item_125_parse_ollama_s_verbose_token_stats_from_the_captured_session_transcript`. Proof deferred to slice closeout.
- request-AC8 -> `item_125_parse_ollama_s_verbose_token_stats_from_the_captured_session_transcript`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_062_track_token_usage_for_interactive_ollama_sessions`
- Product brief(s): `prod_048_ollama_sessions_report_real_token_usage`
- Architecture decision(s): (none yet)
