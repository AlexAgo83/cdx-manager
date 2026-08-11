## task_062_orchestrate_the_per_session_working_directory - Orchestrate the per-session working directory
> From version: 0.18.5
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 80%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-11 13:47:58

# AI Context
- Summary: One resolution point feeds every provider's directory; this adds the explicit argument, the narrow prompt, and the per-run record.
- Keywords: cwd resolution, launch picker, run record, adr_007
- Use when: Implementing req_051. Read adr_007 first: it fixes the shape of the recorded fact and the privacy boundary.
- Skip when: Any work that consumes the recorded directory rather than producing it.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.
- `adr_007` fixes the shape before any code: one resolved absolute path recorded on the run, every other property derived at read time, only a basename crossing to a companion, and a missing record never substituted by the current directory. Read it first.
- Established by inspection, so it does not need rediscovering: the directory is decided at one line per entry point — `src/commands/launch.py:130` (`cwd = ctx.get("cwd") or os.getcwd()`), the headless builder, and `cdx run` — and all three hand it to `_build_launch_spec(session, cwd=...)`. Every provider receives it as `options.cwd`; Codex additionally receives `--cd`. This is one resolution function, not per-provider plumbing.
- The record goes where the run already is: `start_session_runtime` in `src/session_service.py` keeps `runId`, `startedAt`, `pid`, `command`, `label` and `transcriptPath`, and no directory. That absence is the whole gap.
- Why a home-directory launch is worse than merely unhelpful: with no `.git` above it, Codex's project-root resolver returns the home directory itself and loads `~/.codex/` as an untrusted *project* layer, rejecting keys that are only valid at user level. That is upstream issue openai/codex#9932, still open, and not ours to fix — it is the evidence that launching there is a real failure and not a preference.
- SETTLED: the explicit argument is `--dir`. Not positional, because `cdx <name>` already takes an initial prompt positionally and telling a path from a prompt only works while the path exists; not `--cd`, which is Codex's name for it and matches nothing else in cdx.
- SETTLED: the choice is offered only when the directory is exactly the home directory, or `/`. A missing project marker was considered and rejected: it catches more cases at the price of interrupting launches that were already correct, and the failure being fixed is specifically the accidental launch into a home. Widening it later is cheap; a false prompt fifty times a day is not.

# Plan
- [ ] 1. 1. Trace how the directory reaches each provider today, interactively and headlessly, and where the other launch settings are stored and rendered.
- [ ] 2. 2. Add the setting, its validation, and its place in the configuration and JSON surfaces.
- [ ] 3. 3. Honour it at launch with a per-launch override, and refuse before starting a provider when it has gone.
- [ ] 4. 4. Add focused tests per provider for recorded, overridden, absent and missing; then run project validation.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_100_record_and_honour_a_per_session_working_directory`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_100_record_and_honour_a_per_session_working_directory`. Proof deferred to slice closeout.
- request-AC2 -> `item_100_record_and_honour_a_per_session_working_directory`. Proof deferred to slice closeout.
- request-AC3 -> `item_100_record_and_honour_a_per_session_working_directory`. Proof deferred to slice closeout.
- request-AC4 -> `item_100_record_and_honour_a_per_session_working_directory`. Proof deferred to slice closeout.
- request-AC5 -> `item_100_record_and_honour_a_per_session_working_directory`. Proof deferred to slice closeout.
- request-AC6 -> `item_100_record_and_honour_a_per_session_working_directory`. Proof deferred to slice closeout.
- request-AC7 -> `item_100_record_and_honour_a_per_session_working_directory`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_051_launch_a_session_in_the_directory_it_belongs_to`
- Product brief(s): `prod_038_sessions_that_know_what_they_are_working_on`
- Architecture decision(s): `adr_007_what_cdx_records_about_where_a_run_happened`
