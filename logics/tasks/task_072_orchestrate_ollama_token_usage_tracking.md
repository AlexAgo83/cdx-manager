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

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: orchestrate, ollama, token, usage, tracking
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Confirm ollama's real `--verbose` output format with a live `ollama run <model> --verbose` call in the dev/CI environment; capture a real sample as the test fixture instead of a guessed format.
- [ ] 2. Add `--verbose` to the ollama launch args in `provider_runtime.py` and confirm it doesn't alter existing prompt/model/extra-arg handling.
- [ ] 3. Add the `_ollama_usage` parser to `interactive_usage.py`, wired through the cdx-generated transcript path for ollama specifically, leaving codex/claude's directory-walk path untouched.
- [ ] 4. Add `ollama` to `run_usage.SUPPORTED_PROVIDERS`.
- [ ] 5. Write fixture-based tests: verbose block present, verbose block absent/malformed, and a claude/codex regression check.
- [ ] 6. Manually verify `cdx stats`/`cdx history` show non-zero ollama tokens after one real launch.
- [ ] 7. Record the antigravity dead-end explicitly in code comments or README near the usage-extraction code, not just in this corpus, so a future contributor doesn't re-attempt it without reading this task.
- [ ] 8. Run the full test suite, then `logics-manager lint --require-status` and `logics-manager audit --group-by-doc` before closeout.
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

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_062_track_token_usage_for_interactive_ollama_sessions`
- Product brief(s): `prod_048_ollama_sessions_report_real_token_usage`
- Architecture decision(s): (none yet)
