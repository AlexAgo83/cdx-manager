## task_062_orchestrate_the_per_session_working_directory - Orchestrate the per-session working directory
> From version: 0.18.5
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 90%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-11 13:47:58
> Owner: Codex

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
- [x] 1. 1. Trace how the directory reaches each provider today, interactively and headlessly, and where the other launch settings are stored and rendered.
- [x] 2. 2. Add the setting, its validation, and its place in the configuration and JSON surfaces.
- [x] 3. 3. Honour it at launch with a per-launch override, and refuse before starting a provider when it has gone.
- [x] 4. 4. Add focused tests per provider for recorded, overridden, absent and missing; then run project validation.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_100_record_and_honour_a_per_session_working_directory`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: `--dir` is honoured by interactive and headless launch tests in `7a80650`.
- request-AC2 -> This task. Proof: home/root interactive selection reads prior run directories without changing normal launches in `7a80650`.
- request-AC3 -> This task. Proof: the chooser only runs for home or `/`; targeted launch tests passed in `7a80650`.
- request-AC4 -> This task. Proof: JSON returns `cwd` and non-TTY launch reports it in `7a80650`.
- request-AC5 -> This task. Proof: missing explicit paths fail before authentication/provider launch in `7a80650`.
- request-AC6 -> This task. Proof: runtime and history records carry `cwd` in `7a80650`.
- request-AC7 -> This task. Proof: session status rows expose the active runtime `cwd` in `7a80650`.
- request-AC8 -> This task. Proof: targeted pytest (181 passed) and `npm run lint` passed for `7a80650`.

# Validation
- (no validation recorded yet)
- command: `npm run test:py -- test/test_commands_launch_py.py test/test_session_service_py.py test/test_commands_runs_py.py && npm run lint` | result: passed | date: 2026-08-11
- Finish workflow executed on 2026-08-11.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-11.
- Linked backlog item(s): `item_100_record_and_honour_a_per_session_working_directory`
- Related request(s): `req_051_launch_a_session_in_the_directory_it_belongs_to`

# Links
- Request: `req_051_launch_a_session_in_the_directory_it_belongs_to`
- Product brief(s): `prod_038_sessions_that_know_what_they_are_working_on`
- Architecture decision(s): `adr_007_what_cdx_records_about_where_a_run_happened`
