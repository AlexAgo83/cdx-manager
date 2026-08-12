## task_066_orchestrate_writable_and_cancellable_launch_directory_selection - Orchestrate writable and cancellable launch-directory selection
> From version: 0.18.6
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-13 01:01:31
> Owner: Codex

# AI Context
- Summary: Deliver one shared selector repair: manual Other input with existing validation, plus clean cancellation before a provider can start.
- Keywords: orchestrate, writable, cancellable, launch, directory, selection
- Use when: Implementing the narrow interactive launch-directory repair after the active tray recovery task.
- Skip when: The work concerns terminal applications, alert routing, or a non-interactive CDX launch.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Reproduce the interactive menu from a terminal and pin the current selection and Ctrl-C behavior with focused command tests.
- [x] 2. Add the smallest Other-path loop using existing normalization and validation, preserving every non-interactive path.
- [x] 3. Handle interruption only at the interactive selection boundary, prove no launch or mutation follows it, and run project validation.
- [x] 4. Update Logics indicators and record validation evidence before closeout.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_109_add_a_validated_other_path_to_the_interactive_launch_directory_prompt`
- `item_110_make_interactive_launch_directory_cancellation_a_clean_no_op`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: date: 2026-08-13 | command: `npm run test:py -- test/test_commands_launch_py.py` | result: passed | The Other menu choice returns a realpath-normalized valid directory. Source: `ae04d03`
- request-AC2 -> This task. Proof: date: 2026-08-13 | command: `npm run test:py -- test/test_commands_launch_py.py` | result: passed | An invalid Other path is reported and the path prompt retries without launching. Source: `ae04d03`
- request-AC4 -> This task. Proof: date: 2026-08-13 | command: `npm run test:py -- test/test_commands_launch_py.py` | result: passed | Existing launch and resume directory behaviour remains covered by the launch command suite. Source: `ae04d03`
- request-AC5 -> This task. Proof: date: 2026-08-13 | command: `npm test && npm run lint` | result: passed | Focused command coverage plus full project tests and lint passed. Source: `ae04d03`
- request-AC3 -> This task. Proof: date: 2026-08-13 | command: `PTY source-cli cancellation smoke` | result: passed | PTY Ctrl-C exits 130 without traceback or session mutation at the selection boundary. Source: `ae04d03`
- request-AC4 -> This task. Proof: date: 2026-08-13 | command: `npm run test:py -- test/test_commands_launch_py.py` | result: passed | Existing launch and resume directory behaviour remains covered by the launch command suite. Source: `ae04d03`
- request-AC5 -> This task. Proof: date: 2026-08-13 | command: `npm test && npm run lint` | result: passed | Focused command coverage plus full project tests and lint passed. Source: `ae04d03`

# Validation
- (no validation recorded yet)
- command: `npm test && npm run lint` | result: passed | date: 2026-08-13 | note: PTY source-cli smoke: Ctrl-C at the real selection prompt exited 130, printed no traceback, and left session state unchanged.
- Finish workflow executed on 2026-08-13.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-13.
- Linked backlog item(s): `item_109_add_a_validated_other_path_to_the_interactive_launch_directory_prompt`, `item_110_make_interactive_launch_directory_cancellation_a_clean_no_op`
- Related request(s): `req_055_make_interactive_launch_directory_selection_writable_and_cancellation_safe`

# Links
- Request: `req_055_make_interactive_launch_directory_selection_writable_and_cancellation_safe`
- Product brief(s): `prod_042_recoverable_interactive_cdx_launch_choices`
- Architecture decision(s): (none yet)

# Evidence
- AC1 | date: 2026-08-13 | command: `npm run test:py -- test/test_commands_launch_py.py` | result: passed | The Other menu choice returns a realpath-normalized valid directory.
- AC2 | date: 2026-08-13 | command: `npm run test:py -- test/test_commands_launch_py.py` | result: passed | An invalid Other path is reported and the path prompt retries without launching.
- AC3 | date: 2026-08-13 | command: `PTY source-cli cancellation smoke` | result: passed | PTY Ctrl-C exits 130 without traceback or session mutation at the selection boundary.
- AC4 | date: 2026-08-13 | command: `npm run test:py -- test/test_commands_launch_py.py` | result: passed | Existing launch and resume directory behaviour remains covered by the launch command suite.
- AC5 | date: 2026-08-13 | command: `npm test && npm run lint` | result: passed | Focused command coverage plus full project tests and lint passed.
