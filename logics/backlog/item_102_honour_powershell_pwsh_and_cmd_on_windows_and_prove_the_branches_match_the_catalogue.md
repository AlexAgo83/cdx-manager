## item_102_honour_powershell_pwsh_and_cmd_on_windows_and_prove_the_branches_match_the_catalogue - Honour PowerShell, pwsh and cmd on Windows, and prove the branches match the catalogue
> From version: 0.18.6
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: tray-companion
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: honour, powershell, pwsh, cmd, windows, prove, branches, match, catalogue
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- tray/src/win.rs honours `wt` alone; any other stored name falls back to cmd without a word, so a recorded preference can be a lie.
- Windows needs the shell named as well as the terminal, and the companion hard-codes `cmd /k` invisibly.
- Nothing fails when a name is added to CDX's catalogue without a matching branch in the companion.

# Scope
- In:
  - Add documented launch branches for `powershell`, `pwsh` and `cmd` beside the existing `wt` one, under both the native and WSL transports.
  - Keep the silent-fallback path for a name the build cannot launch, since it remains the only safe behaviour for a stale preference.
  - Add a contract test asserting that the Windows names CDX declares launchable are exactly those the companion implements a branch for.
  - Document, in the module that owns it, that Windows names a shell where the other platforms name an application.
- Out:
  - Adding terminal emulators beyond the four named here.
  - Changing the macOS or Linux launch paths, whose conventions already cover any installed application.
  - Exposing shell arguments or profiles as part of the preference.

# Acceptance criteria
- AC1: Each of `wt`, `powershell`, `pwsh` and `cmd` launches the intended cdx command through its own documented invocation, under native and WSL transports alike.
- AC2: A stored name this build cannot launch still opens the default console rather than doing nothing.
- AC3: A contract test fails when CDX's Windows catalogue and the companion's implemented branches disagree in either direction.
- AC4: The command line is composed by the companion from CDX's own command, never from the preference, which names only the application or shell.
- AC5: The Rust tray test suite and the Python contract suite both pass, with new cases for each added branch.

# AC Traceability
- request-AC4 -> This backlog slice. Proof: AC1: Each of `wt`, `powershell`, `pwsh` and `cmd` launches the intended cdx command through its own documented invocation, under native and WSL transports alike.
- request-AC5 -> This backlog slice. Proof: AC2: A stored name this build cannot launch still opens the default console rather than doing nothing.
- request-AC6 -> This backlog slice. Proof: AC3: A contract test fails when CDX's Windows catalogue and the companion's implemented branches disagree in either direction.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_039_a_tray_whose_terminal_preference_is_discoverable_and_honest`
- Architecture decision(s): (none yet)
- Request: `req_052_let_the_operator_choose_the_tray_s_target_terminal_on_every_platform`
- Primary task(s): `task_063_deliver_a_discoverable_and_honest_tray_terminal_choice`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
