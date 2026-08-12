## req_052_let_the_operator_choose_the_tray_s_target_terminal_on_every_platform - Let the operator choose the tray's target terminal on every platform
> From version: 0.18.6
> Schema version: 1.0
> Status: Draft
> Understanding: 95%
> Confidence: 90%
> Complexity: Medium
> Theme: tray-companion
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: The tray's terminal preference exists and works but is reachable only through a CLI command nobody discovers, and on Windows it is honoured for `wt` alone — every other name falls back to cmd in silence. This makes the choice visible in the menu and makes an offered choice an honoured one.
- Keywords: tray, terminal, preference, submenu, windows, powershell, discovery, snapshot
- Use when: Working on how the tray opens a session, on the terminal preference and its catalogue, or on the snapshot keys and menu entries that carry it.
- Skip when: Working on which terminal a headless or CLI launch uses, on interactive terminal titles, or on any tray surface other than the terminal choice.

# Needs
- Change which terminal application the tray's session rows open, from the tray menu itself, on macOS, Linux and Windows.
- Discover the available choices from the CLI without reading the source or guessing a name.
- Trust that a terminal offered as a choice is a terminal that will actually open.

# Context
- The preference exists and works but is reachable only through `cdx tray terminal set <name>`, so an operator who never read the help has the platform default forever.
- The preference is deliberately an application name and never a command line; nothing about this delivery may weaken that, because the value is writable by anything that can write CDX's state.
- macOS and Linux have a universal launch convention (`open -a`, `-e`), so any installed terminal can be honoured there; Windows has none, and the companion special-cases `wt` alone.
- Windows conflates two axes the other platforms do not: the terminal application (wt, conhost) and the shell it runs (cmd, powershell, pwsh). The companion already hard-codes `cmd /k` without telling anyone.
- PowerShell and pwsh are not terminals but shells, and both document a launch-with-a-command form (`-NoExit -Command`), so they can be honoured exactly as `wt` already is.
- A checked menu item that records a choice the companion cannot honour is worse than no submenu: the fallback is silent, so the operator sees a tick and gets a different terminal.
- Candidate discovery is a snapshot and can become stale before a click. A missing selected terminal at action time must report an unavailable action or use only the explicit system-default choice; it must never silently substitute another named terminal.
- Candidate discovery and execution must describe the companion transport that will execute them. In particular, a Windows host and a WSL CDX process cannot claim availability on behalf of one another.

# Acceptance criteria
- AC1: The tray menu offers a terminal submenu on macOS, Linux and Windows, listing the candidates with the current choice ticked and an explicit system-default entry.
- AC2: Choosing an entry records the preference through CDX rather than in the companion, and the tick reflects what was stored rather than what was clicked.
- AC3: `cdx tray terminal list` prints the candidates, marks the current choice, and names the platform default, in both human and JSON output.
- AC4: A candidate is offered only when this build knows how to launch it and it is present on the host; anything else is absent rather than drawn and silently ignored.
- AC5: Windows honours `wt`, `powershell`, `pwsh` and `cmd` through each one's documented invocation, under both native and WSL transports.
- AC6: The launchable names are declared once, in CDX, and a contract test fails when the companion's Windows branches and that declaration disagree.
- AC7: The terminal preference still stores an application name and never a command, and every path added here re-validates through the existing rule.
- AC8: A companion older than this delivery reads the extended snapshot unchanged, and an operator with no preference keeps the platform default.
- AC9: If a previously offered named terminal is absent when clicked, CDX reports that outcome without falling back to a different named terminal; the explicit system-default choice remains the sole fallback path.
- AC10: Tests prove candidate availability and launch execution under each native and WSL transport boundary rather than treating the CDX process PATH as the companion host PATH.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_039_a_tray_whose_terminal_preference_is_discoverable_and_honest`
- Architecture decision(s): (none yet)

# References
- User request: changing the target terminal must be possible from a tray submenu on every platform, plus a CLI discovery command
- src/tray_terminal.py: storage and name validation already exist; the preference is an application name, never a command
- src/tray_contract.py:226 build_snapshot already carries `terminal` but not the candidates
- src/commands/tray.py:403 `cdx tray terminal set|clear|status` exists and is the only way to discover the preference
- tray/src/win.rs:298 open_terminal_in honours only `wt`; every other name falls back to cmd without saying so
- tray/src/mac.rs:192 and tray/src/linux.rs:287 launch a preferred application through a platform-wide convention (`open -a`, `-e`)
- tray/src/menu.rs Entry::Submenu and Entry::Check already exist, used by session rows and the alert mute

# Backlog
- `item_101_declare_the_launchable_terminals_in_cdx_and_publish_the_candidates`
- `item_102_honour_powershell_pwsh_and_cmd_on_windows_and_prove_the_branches_match_the_catalogue`
- `item_103_offer_the_terminal_choice_as_a_tray_submenu`
