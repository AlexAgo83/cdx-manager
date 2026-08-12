## req_055_make_interactive_launch_directory_selection_writable_and_cancellation_safe - Make interactive launch-directory selection writable and cancellation-safe
> From version: 0.18.6
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Low
> Theme: CLI usability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-13 01:01:30

# AI Context
- Summary: Keep the compact recent-directory chooser, but allow one validated manual path and make Ctrl-C terminate the choice without entering any launch path.
- Keywords: interactive, launch, directory, selection, writable, cancellation, safe
- Use when: Changing interactive CDX launch-directory selection in src/commands/launch.py.
- Skip when: Building a directory browser, changing tray terminal preferences, or altering non-interactive launch arguments.

# Needs
- When CDX offers recently used launch directories, an operator can only choose a displayed number. They need one explicit Other option to enter a valid directory that is not already listed.
- Pressing Ctrl-C at the interactive directory prompt currently raises KeyboardInterrupt through the top-level CLI and prints a Python traceback. Cancelling a choice must leave no launch, no saved state change, and no traceback.

# Context
- _launch_directory in src/commands/launch.py builds the numbered recent-directory menu before any provider process is started. The change belongs at that boundary, not in each launch caller.
- The typed directory must use the same realpath and is-directory validation as an explicit directory argument. An empty typed path returns to the menu rather than silently choosing an unrelated directory.
- Cancellation is a normal interactive outcome. CDX should print one concise cancellation line and exit with the conventional interrupted status without persisting a launch directory or emitting a stack trace.

# Acceptance criteria
- AC1: The interactive launch-directory menu includes one clearly labelled Other option that prompts for a path; a valid entered directory is normalized and becomes the launch directory.
- AC2: An invalid, unreadable, or non-directory Other path reports a concise validation message and re-prompts without launching a provider or changing durable session state.
- AC3: Ctrl-C at either the choice prompt or the Other-path prompt exits cleanly with no Python traceback, no provider launch, and no session or directory mutation.
- AC4: Existing numbered choices, the default current directory, explicit --dir behavior, JSON/non-interactive behavior, and recent-directory ordering remain unchanged.
- AC5: Focused command tests cover valid Other input, invalid retry, cancellation at both prompts, and unchanged legacy selection behavior; project and Logics validation pass.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_042_recoverable_interactive_cdx_launch_choices`
- Architecture decision(s): (none yet)

# References
- src/commands/launch.py
- src/cli.py
- test/test_commands_launch_py.py

# Backlog
- `item_109_add_a_validated_other_path_to_the_interactive_launch_directory_prompt`
- `item_110_make_interactive_launch_directory_cancellation_a_clean_no_op`
