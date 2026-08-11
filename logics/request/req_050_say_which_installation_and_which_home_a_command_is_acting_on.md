## req_050_say_which_installation_and_which_home_a_command_is_acting_on - Say which installation and which home a command is acting on
> From version: 0.18.5
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Diagnostics
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: say, installation, home, command, acting
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Needs
- `cdx update` run from inside a cdx session reports success and updates a copy nobody runs. The session's home is redirected so provider auth stays isolated, so `$HOME/.local` is the session's, not the operator's — and the installer correctly installs where it was pointed. Measured while releasing 0.18.5: it reported updated, and the operator's own cdx stayed on the previous version.
- The same redirection makes a hook publish into a store no companion watches, so an alert is delivered directly while a tray is plainly running.
- A companion crossing into WSL resolves a non-login PATH and can answer about an older cdx than the operator's terminal ever sees.
- Three symptoms, one cause, and in every case the tool reported success about something other than what the operator meant. A diagnosis exists — run_002 — but a runbook is what someone reads after losing an hour.

# Context
- None of these is a bug in what the code does: the installer installs where HOME points, the hook writes where CDX_HOME points, and the companion runs what PATH resolves. Each is correct and none of them says which one it picked.
- The information is free at the moment it matters: the command already knows the prefix it is about to write to, the store it is about to publish into, and the binary it is about to run.
- `cdx tray doctor` already exists as the place diagnostics live, and already reports drift between CDX and the companion. It does not report which CDX the companion actually reaches, which is the one it cannot see for itself.
- The fix must not become noise. A line on every command would be ignored within a day; what is wanted is a line when the target is not the obvious one.

# Acceptance criteria
- AC1: A command that installs, updates or removes says which prefix it acted on, and says so in its JSON result as well as its text output.
- AC2: When it is acting on a session profile rather than the operator's own home, it says so explicitly and names both, rather than reporting a bare success.
- AC3: `cdx tray doctor` reports the cdx the companion actually resolves, including across WSL, and the store it publishes into.
- AC4: A normal invocation from a normal shell gains no new noise: the extra line appears when the target is surprising, not on every run.
- AC5: Nothing new is written, moved or refused because of this; it reports and never acts.
- AC6: Focused tests cover a redirected home, an inherited CDX_HOME, and a companion resolving a different binary; project validation passes.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_037_commands_that_name_what_they_are_about_to_touch`
- Architecture decision(s): (none yet)

# References
- src/update_manager.py
- src/commands/maintenance.py
- src/commands/tray.py
- run_002_finding_out_which_cdx_and_which_home_you_are_talking_to

# Backlog
- `item_098_name_the_prefix_an_install_or_update_acted_on`
- `item_099_report_the_cdx_and_store_the_companion_actually_reaches`
