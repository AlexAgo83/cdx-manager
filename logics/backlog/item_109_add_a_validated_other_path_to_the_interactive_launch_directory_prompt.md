## item_109_add_a_validated_other_path_to_the_interactive_launch_directory_prompt - Add a validated Other path to the interactive launch-directory prompt
> From version: 0.18.6
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 10%
> Complexity: Low
> Theme: CLI usability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-13 01:01:30

# AI Context
- Summary: Reuse explicit-directory validation behind one Other entry instead of treating the bounded recent list as the only possible launch location.
- Keywords: add, validated, other, path, interactive, launch, directory, prompt
- Use when: Adding typed directory input to the interactive launch menu.
- Skip when: Adding a graphical picker, directory scanning, or durable favourites.

# Problem
- The current selector lists recent paths but cannot reach a valid directory outside that bounded list.
- Ad-hoc validation would drift from the explicit launch-directory path.

# Scope
- In:
  - Add one Other menu option and a path prompt to _launch_directory.
  - Reuse realpath and is-directory validation, with a concise retry message for invalid input.
  - Add focused command tests for valid Other input, invalid retry, and preserved numeric/default choices.
- Out:
  - A directory picker, recursive discovery, persistent favourites, or a changed command-line directory contract.

# Acceptance criteria
- AC1: Other accepts a valid directory and returns its normalized path to the existing launch flow.
- AC2: Invalid paths retry safely and do not launch a provider.
- AC3: Numbered, default, explicit, JSON, and non-interactive paths retain their current behavior.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: Other accepts a valid directory and returns its normalized path to the existing launch flow.
- request-AC2 -> This backlog slice. Proof: AC2: Invalid paths retry safely and do not launch a provider.
- request-AC4 -> This backlog slice. Proof: AC3: Numbered, default, explicit, JSON, and non-interactive paths retain their current behavior.
- request-AC5 -> This backlog slice. Proof: AC3: Numbered, default, explicit, JSON, and non-interactive paths retain their current behavior.

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
