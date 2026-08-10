## req_033_make_agent_notification_controls_discoverable_and_self_explanatory - Make agent notification controls discoverable and self-explanatory
> From version: 0.17.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Notifications
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: Make agent notification controls discoverable and self-explanatory
- Keywords: request-chain-scaffold, make agent notification controls discoverable and self-explanatory, development-ready
- Use when: You need to implement or review the scaffolded workflow for Make agent notification controls discoverable and self-explanatory.
- Skip when: The change is unrelated to this scaffolded request chain.

# Needs
- The notification feature has two user-facing intents with different meanings: per-session agent attention alerts and a one-shot next-ready alert. The current command list exposes their internal names without making that distinction easy to understand.
- Turning agent notifications on or off currently returns a generic launch-settings update. It does not clearly say when the change takes effect, that provisioning happens on the next interactive launch, or that one supported provider requires hook review before its hooks run.
- The internal hook target appears in the main CLI usage beside user commands, while running it manually produces no useful explanation. The supported setup path needs to be discoverable from the CLI, not only from the README.

# Context
- src/cli.py lists cdx ready and cdx notify in the root usage. The latter is a provider hook target, whereas cdx set <name> --notify on is the user setup command.
- src/commands/settings.py always emits the generic Updated launch settings message before the shared launch-settings table. src/cli_helpers.py renders Notify as an unqualified on/off value and supplies one broad settings example.
- src/commands/launch.py already knows whether hook provisioning happened and, for one provider, tells the user to review the hook once. This is the correct lifecycle point for a completion message, not a new persistent installation-state store.
- README.md documents agent notifications and next-ready notifications in separate prose, but the root help and main screen do not give a concise task-oriented route to either behavior.
- cdx notify must remain a non-failing hook target when called by a provider; direct terminal invocation can be detected without changing that hook contract.

# Acceptance criteria
- AC1: Root help and the main screen present a compact Notifications section that distinguishes agent attention alerts from next-ready alerts and gives the exact setup command for each user-facing action.
- AC2: The internal hook target is not presented as a normal interactive command; a direct TTY invocation explains that it is provider-called and points to the setup command, while hook invocation stays silent and exits successfully.
- AC3: Setting agent notifications on or off produces a focused confirmation that names the affected session or sessions, states that provisioning or removal occurs on the next interactive launch, and preserves the existing structured JSON contract.
- AC4: After a launch provisions hooks, user-facing output explains the resulting next action when review is required; when hooks are already present or the delivery channel is unavailable, output remains accurate without claiming an active notification state that was not verified.
- AC5: Configuration output makes the meaning of the Notify preference understandable without introducing a second notification command or a persistent hook-installation state model.
- AC6: README command reference and notification guidance use the same terminology and examples as the CLI, including the distinction between cdx set <name> --notify on, cdx ready, and the internal cdx notify target.
- AC7: Focused CLI, settings, launch, and documentation tests cover the new guidance and preserve the no-failure hook behavior; the full project validation suite passes.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_023_clear_notification_controls`
- Architecture decision(s): (none yet)

# References
- src/cli.py
- src/cli_render.py
- src/cli_helpers.py
- src/commands/settings.py
- src/commands/launch.py
- src/agent_notify.py
- README.md
- test/test_cli_contract_py.py
- test/test_commands_settings_py.py
- test/test_commands_launch_py.py
- test/test_main_screen_py.py

# Backlog
- `item_077_clarify_notification_setup_lifecycle_feedback_and_documentation`
