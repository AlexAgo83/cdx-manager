## req_030_tell_the_user_which_parallel_cdx_session_finished_or_is_waiting_without_watching_terminals - Tell the user which parallel cdx session finished or is waiting, without watching terminals
> From version: 0.15.1
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Notifications
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-09 17:16:23

# Needs
- Running several cdx sessions in parallel across different repositories is the normal way this tool is used, and it is the one case cdx does not support: the only way to learn that an agent finished, or that it is blocked waiting for an answer, is to keep looking at every terminal.
- Both underlying CLIs already emit that event — Claude Code through its `Stop` and `Notification` hooks, Codex through the `notify` key in `config.toml` — and cdx already owns the home directory those settings live in, so it is the only component that can wire them per session without touching the user's personal configuration.
- A notification is only useful here if it says *which* session and *which* repository, and cdx is the only party that knows the session name. A hand-written hook cannot supply it.

# Context
- `send_desktop_notification` (`src/notify.py:158`) already dispatches across platforms: `osascript` on macOS, `notify-send` on Linux, a PowerShell message box on Windows, with escaping helpers for each. It is reached today only by the quota-reset flow and is reusable as-is.
- `_home_env_overrides` (`src/provider_runtime.py:107`) sets `HOME` — plus `USERPROFILE`/`HOMEDRIVE`/`HOMEPATH` on Windows — to the session's `authHome` for every launch. So `<authHome>/.claude/settings.json` is a file cdx owns per session. For Codex the path is `<authHome>/config.toml`, not `<authHome>/.codex/config.toml`: cdx sets `CODEX_HOME` to `authHome` directly (`src/provider_runtime.py:981`), so `authHome` *is* the Codex home. Either way, writing hooks there cannot collide with the user's own `~/.claude` or `~/.codex`.
- `handle_launch` (`src/commands/launch.py:80`) is the single point every interactive launch and resume passes through before `_run_interactive_provider_command`, which makes it the natural place for an idempotent write: existing sessions pick the hooks up on their next launch, so no migration step is needed.
- The launch settings machinery already supports exactly this shape of toggle: `--rtk` and `--logics` are on/off values parsed by `_parse_fast_value` (`src/cli_args.py:247`), stored per session through `set_launch_settings`, and clearable through `cdx unset`. A `--notify` flag is the same pattern with no new infrastructure.
- The name `cdx notify` is currently taken by quota-reset notifications: `cdx notify <name> --at-reset` and `cdx notify --next-ready` (`src/notify.py:19`, dispatched at `src/cli.py:156`). That surface answers 'when does my quota come back', which `cdx status` already answers directly, and in practice the only form anyone types is `cdx ready` — documented at `README.md:345` as shorthand for `cdx notify --schedule --next-ready`.
- The scope decision taken with the user: `notify` is reassigned to the new hook target, the `--at-reset`/`--next-ready` CLI surface is retired from parsing and documentation, and the underlying logic stays reachable through `cdx ready`. Deleting the remaining ~250 lines of launchd/systemd/schtasks scheduling is deliberately left as a separate later decision, once there is evidence `cdx ready` is unused too.
- Windows needs a different notifier than the one that exists. `_send_windows_notification` (`src/notify.py:186`) raises a blocking `System.Windows.Forms.MessageBox` and — unlike the macOS and Linux paths, which pass `timeout=5` — calls `spawn_sync` with no timeout at all. Fired once by a scheduled quota task that is merely ugly; fired as a hook on every agent turn it blocks the hook process until the user clicks OK, and the provider waits on its hooks. This is the one platform where the current notifier actively breaks AC8 rather than merely degrading.
- The hook command cannot be the bare name `cdx`. Codex spawns its `notify` argv directly rather than through a shell, and on Windows npm installs a `cdx.cmd` shim rather than an executable named `cdx`; pipx and uv installs can likewise leave `cdx` off the PATH the provider inherits. `_scheduled_notify_argv` (`src/notify.py:246`) already solves this for the quota flow by resolving `CDX_BIN` or `shutil.which("cdx")` and writing the resolved path.
- Linux desktop notifications need a session bus. Over SSH, in a container, or on a headless box there is no D-Bus session and `notify-send` cannot deliver; the same is true of `osascript` in an SSH session on macOS. Silence is the correct outcome there, but it should be a known and stated outcome rather than a bug report.
- Notifications are on by default, because a feature that must be discovered and enabled will not be. `cdx set <name> --notify off` turns them off, and cdx removes the hooks it wrote at the next launch of that session.

# Acceptance criteria
- AC1: `cdx notify` is a hook target that reads a hook payload on standard input and raises a desktop notification identifying the cdx session name and the working directory the agent was running in.
- AC2: Launching a session provisions the hook configuration into that session's own home directory, for both Claude Code and Codex, without modifying any configuration outside the session's home.
- AC3: Provisioning is idempotent: launching the same session repeatedly leaves the configuration unchanged, and a session created before this change is provisioned on its next launch with no migration step.
- AC4: Provisioning preserves any other content already present in the session's `settings.json` or `config.toml`, including hooks the user added themselves.
- AC5: Notifications are enabled by default and can be turned off per session through the existing launch settings commands; turning them off removes the hooks cdx wrote, at the next launch of that session.
- AC6: A notification raised while several sessions run in parallel distinguishes them, naming both the session and the repository directory.
- AC7: The quota-reset `cdx notify --at-reset` and `cdx notify --next-ready` command surface is retired from the CLI and the README, while `cdx ready` keeps working exactly as it does today.
- AC8: A failure in the notification path — an absent notifier binary, an unreadable or malformed hook payload, an unwritable configuration file — never fails or delays the launch or the agent turn.
- AC9: The Windows notification path is non-blocking and bounded in time, so a notification the user never dismisses cannot hold up an agent turn.
- AC10: The provisioned hook command resolves to cdx on each platform's supported install paths, including a Windows npm install where `cdx` is a `.cmd` shim and installs where cdx is not on the provider's inherited PATH.
- AC11: On a host with no desktop notification channel available — a headless or SSH Linux session, or any platform whose notifier is missing — the agent turn completes normally and nothing is raised.
- AC12: The README documents the notification behavior, how to turn it off, the new meaning of `cdx notify`, and the per-platform delivery caveats.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_020_know_which_parallel_session_needs_you`
- Architecture decision(s): (none yet)

# References
- src/notify.py
- src/provider_runtime.py
- src/commands/launch.py
- src/commands/settings.py
- src/cli_args.py
- src/cli.py
- test/test_notify_py.py
- README.md

# AI Context
- Summary: Tell the user which parallel cdx session finished or is waiting, without watching terminals
- Keywords: request-chain-scaffold, tell the user which parallel cdx session finished or is waiting, without watching terminals, development-ready
- Use when: You need to implement or review the scaffolded workflow for Tell the user which parallel cdx session finished or is waiting, without watching terminals.
- Skip when: The change is unrelated to this scaffolded request chain.

# Backlog
- `item_073_reassign_cdx_notify_to_the_agent_event_hook_target`
- `item_074_provision_and_revoke_provider_hooks_in_each_session_s_home_at_launch`
