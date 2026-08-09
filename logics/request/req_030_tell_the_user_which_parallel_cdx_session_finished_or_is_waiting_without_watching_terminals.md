## req_030_tell_the_user_which_parallel_cdx_session_finished_or_is_waiting_without_watching_terminals - Tell the user which parallel cdx session finished or is waiting, without watching terminals
> From version: 0.15.1
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Notifications
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-09 18:08:20

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
- WSL is the case the current notifier silently fails. Inside WSL `sys.platform` reads `linux`, so `send_desktop_notification` takes the `notify-send` branch — but a plain WSL2 distribution has no session bus and no desktop, so nothing is delivered and nothing is reported. The repository has no WSL handling at all today (`grep -i wsl` over `src/`, `README.md` and `docs/` returns nothing), which is acceptable for a quota alert nobody depends on and not acceptable for the feature this request exists to provide. Delivery to the Windows notification centre from WSL goes through Windows interop — invoking `powershell.exe`, which WSL exposes on the PATH when interop is enabled — and WSLg on Windows 11 is a second sub-case where a session bus may in fact be present.
- Reaching the Windows notifier through WSL interop inherits its blocking-dialog problem and worsens it: a modal on the Windows desktop would hold open an agent turn running inside the Linux distribution, across the boundary, with nothing in the WSL terminal explaining why.
- Codex 0.147 has replaced the `notify` key with a hooks system whose events and payload match Claude Code's — `hooks.json`, `Stop`, `Notification`, `session_end` — and refers to the old key internally as `legacy_notify`. Both providers therefore share one contract, and there is no need to support two payload shapes on current versions.
- Codex will not run a hook it has not been told to trust. The binary carries a `HookTrustStatus`, a persisted `hooks.state`, and a `--dangerously-bypass-hook-trust` flag described as running "enabled hooks without requiring persisted hook trust". A `hooks.json` that cdx writes on its own therefore produces blocked hooks: no notification, no error, no trace. This is the same silent-success failure mode as an unregistered toast identifier, one step earlier in the chain, and it would affect every platform.
- Installing a hook on a host that cannot deliver a notification buys nothing and costs something: a configuration write, and under Codex an approval prompt for a feature that would show nothing either way. Provisioning is therefore conditional on the host having a usable delivery channel, which is the same question `cdx notify` has to answer at delivery time — one predicate, two callers. Because provisioning re-runs on every launch and is idempotent, the answer is re-evaluated for free: a host that gains a channel later is provisioned at its next launch with no action from the user.
- The decision taken is that cdx writes the hook and the user approves it once per session profile, rather than cdx writing the provider's trust state on the user's behalf. Trust is a guard the provider put there deliberately; cdx owning the directory is not a reason to answer that question for the user. The cost is a one-time approval per profile, and the consequence for this request is that provisioning is not silent: cdx has to say what it installed and what remains to be approved, or the feature appears broken to someone who was promised it needed no setup.
- The two providers hand their payload over differently: Claude Code writes the hook JSON to the hook process's standard input, while Codex passes it to the `notify` program as a command-line argument. A hook target that reads only one of the two works for one provider and silently does nothing for the other.
- The headless path shares the same home as the interactive one. `_run_headless_provider_command` (`src/provider_runtime.py:887`) sets the same `HOME` and `CODEX_HOME` as an interactive launch, so it reads the same configuration files and fires the same hooks. Left alone, a script issuing fifty `cdx run --json` calls would raise fifty desktop notifications. The decision taken is that headless runs do not notify: their caller already learns of completion from the return value, and a caller who wants more can add it in one line at its own call site. Since the session name has to reach the hook through the environment anyway, the same variable carries the suppression, and no new flag is needed.
- Retiring the `--at-reset` and `--next-ready` surface is a breaking change to a documented command, so it needs a changelog entry. The bump itself is not part of this work: in this repository releases are their own `release: X.Y.Z` commit that moves `VERSION`, the README badge, `package.json` and `pyproject.toml` together, and are tracked as their own backlog item. Feature work leaves the entry; the release moves the numbers.
- The delivery mechanism chosen for Windows is a toast pushed through PowerShell, not a dialog. A modal that steals focus on every agent turn is worse than no notification, which rules out both the current `MessageBox` and the cheaper fix of keeping it with a `Wscript.Shell.Popup` timeout. The known trap is that a toast requires a registered `AppUserModelID` or Windows silently drops it; borrowing PowerShell's own identifier avoids both registering one and asking the user to install a module such as BurntToast.
- WSL is then not a third implementation but the Windows one reached differently: the same PowerShell snippet, invoked through `powershell.exe` over interop instead of directly. This is what keeps the per-platform surface to one snippet plus a detection, and it is the reason this request does not need a separate always-running process to centralise platform logic.
- Linux needs almost nothing: `notify-send` is already the right mechanism, already bounded at five seconds, and present wherever libnotify is. Passing an application name so cdx's notifications are attributed to cdx is the only change worth making.
- Linux desktop notifications need a session bus. Over SSH, in a container, or on a headless box there is no D-Bus session and `notify-send` cannot deliver; the same is true of `osascript` in an SSH session on macOS. Silence is the correct outcome there, but it should be a known and stated outcome rather than a bug report.
- Notifications are on by default, because a feature that must be discovered and enabled will not be. `cdx set <name> --notify off` turns them off, and cdx removes the hooks it wrote at the next launch of that session.

# Acceptance criteria
- AC1: `cdx notify` is a hook target that accepts a hook payload in either of the forms its two providers use — Claude Code's on standard input, Codex's as a command-line argument — and raises a desktop notification identifying the cdx session name and the working directory the agent was running in.
- AC2: Launching a session provisions the hook configuration into that session's own home directory, for both Claude Code and Codex, without modifying any configuration outside the session's home.
- AC3: Provisioning is idempotent: launching the same session repeatedly leaves the configuration unchanged, and a session created before this change is provisioned on its next launch with no migration step.
- AC4: Provisioning preserves any other content already present in the session's `settings.json` or `config.toml`, including hooks the user added themselves.
- AC5: Notifications are enabled by default and can be turned off per session through the existing launch settings commands; turning them off removes the hooks cdx wrote, at the next launch of that session.
- AC6: A notification raised while several sessions run in parallel distinguishes them, naming both the session and the repository directory.
- AC7: The quota-reset `cdx notify --at-reset` and `cdx notify --next-ready` command surface is retired from the CLI and the README, while `cdx ready` keeps working exactly as it does today.
- AC8: A failure in the notification path — an absent notifier binary, an unreadable or malformed hook payload, an unwritable configuration file — never fails or delays the launch or the agent turn.
- AC9: The Windows notification path is non-blocking and bounded in time, so a notification the user never dismisses cannot hold up an agent turn.
- AC10: The provisioned hook command resolves to cdx on each platform's supported install paths, including a Windows npm install where `cdx` is a `.cmd` shim and installs where cdx is not on the provider's inherited PATH.
- AC11: A session running inside WSL delivers its notification to the Windows notification centre, rather than taking the plain-Linux path and silently delivering nothing.
- AC12: On a host with no desktop notification channel available — a headless or SSH Linux session, a WSL distribution with interop disabled, or any platform whose notifier is missing — the agent turn completes normally and nothing is raised.
- AC13: A headless run does not raise notifications, so a script issuing many runs stays silent, while interactive launches are unaffected.
- AC14: The breaking retirement of the previous `cdx notify` surface is documented in a changelog entry ready for whoever cuts the next release; bumping the version declarations belongs to that release, not to this work.
- AC15: When cdx installs notification hooks that the provider will not run until the user approves them, cdx says so at launch, naming what to approve, rather than leaving the user with a feature that silently does nothing.
- AC16: On a host with no usable notification channel, no hooks are installed and no approval is requested; if that host later gains one, its next launch installs them.
- AC17: The README documents the notification behavior, how to turn it off, the new meaning of `cdx notify`, and the per-platform delivery caveats including WSL.

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
