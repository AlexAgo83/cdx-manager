## item_110_make_interactive_launch_directory_cancellation_a_clean_no_op - Make interactive launch-directory cancellation a clean no-op
> From version: 0.18.6
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Low
> Theme: CLI reliability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-13 01:01:31

# AI Context
- Summary: Catch only prompt interruption so cancellation has a conventional exit and never leaks a Python traceback or reaches provider launch.
- Keywords: interactive, launch, directory, cancellation, clean
- Use when: Handling Ctrl-C at the launch-directory choice or typed-path prompt.
- Skip when: Broadly changing error handling for unrelated CDX commands.

# Problem
- KeyboardInterrupt from the prompt reaches the Python entry point, exposing an implementation traceback for an ordinary cancelled choice.

# Scope
- In:
  - Handle interruption at the directory-selection boundary and return the conventional interrupted outcome without entering provider launch logic.
  - Cover cancellation at both choice prompts and assert no launch or state mutation.
- Out:
  - Changing cancellation semantics for unrelated commands, swallowing other errors, or converting a cancellation into a default directory launch.

# Acceptance criteria
- AC1: Ctrl-C at either interactive directory prompt prints concise cancellation output with no traceback.
- AC2: Cancellation starts no provider and writes no session or directory state.
- AC3: Other CLI exceptions retain their existing error handling.

# AC Traceability
- request-AC3 -> This backlog slice. Proof: AC1: Ctrl-C at either interactive directory prompt prints concise cancellation output with no traceback.
- request-AC4 -> This backlog slice. Proof: AC2: Cancellation starts no provider and writes no session or directory state.
- request-AC5 -> This backlog slice. Proof: AC3: Other CLI exceptions retain their existing error handling.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_042_recoverable_interactive_cdx_launch_choices`
- Architecture decision(s): (none yet)
- Request: `req_055_make_interactive_launch_directory_selection_writable_and_cancellation_safe`
- Primary task(s): `task_066_orchestrate_writable_and_cancellable_launch_directory_selection`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
