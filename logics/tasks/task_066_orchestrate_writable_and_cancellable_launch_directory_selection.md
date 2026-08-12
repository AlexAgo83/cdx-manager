## task_066_orchestrate_writable_and_cancellable_launch_directory_selection - Orchestrate writable and cancellable launch-directory selection
> From version: 0.18.6
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-13 01:01:31

# AI Context
- Summary: Deliver one shared selector repair: manual Other input with existing validation, plus clean cancellation before a provider can start.
- Keywords: orchestrate, writable, cancellable, launch, directory, selection
- Use when: Implementing the narrow interactive launch-directory repair after the active tray recovery task.
- Skip when: The work concerns terminal applications, alert routing, or a non-interactive CDX launch.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Reproduce the interactive menu from a terminal and pin the current selection and Ctrl-C behavior with focused command tests.
- [ ] 2. Add the smallest Other-path loop using existing normalization and validation, preserving every non-interactive path.
- [ ] 3. Handle interruption only at the interactive selection boundary, prove no launch or mutation follows it, and run project validation.
- [ ] 4. Update Logics indicators and record validation evidence before closeout.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_109_add_a_validated_other_path_to_the_interactive_launch_directory_prompt`
- `item_110_make_interactive_launch_directory_cancellation_a_clean_no_op`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_109_add_a_validated_other_path_to_the_interactive_launch_directory_prompt`. Proof deferred to slice closeout.
- request-AC2 -> `item_109_add_a_validated_other_path_to_the_interactive_launch_directory_prompt`. Proof deferred to slice closeout.
- request-AC4 -> `item_109_add_a_validated_other_path_to_the_interactive_launch_directory_prompt`. Proof deferred to slice closeout.
- request-AC5 -> `item_109_add_a_validated_other_path_to_the_interactive_launch_directory_prompt`. Proof deferred to slice closeout.
- request-AC3 -> `item_110_make_interactive_launch_directory_cancellation_a_clean_no_op`. Proof deferred to slice closeout.
- request-AC4 -> `item_110_make_interactive_launch_directory_cancellation_a_clean_no_op`. Proof deferred to slice closeout.
- request-AC5 -> `item_110_make_interactive_launch_directory_cancellation_a_clean_no_op`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_055_make_interactive_launch_directory_selection_writable_and_cancellation_safe`
- Product brief(s): `prod_042_recoverable_interactive_cdx_launch_choices`
- Architecture decision(s): (none yet)
