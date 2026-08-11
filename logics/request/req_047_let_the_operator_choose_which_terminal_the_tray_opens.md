## req_047_let_the_operator_choose_which_terminal_the_tray_opens - Let the operator choose which terminal the tray opens
> From version: 0.18.4
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Tray usability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: let, operator, choose, terminal, tray, opens
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Needs
- Clicking a session opens whatever terminal the companion decided to use: Terminal.app on macOS, the first of four names that answers on Linux. Someone who works in iTerm, Ghostty, Kitty, WezTerm or Alacritty gets a second terminal application opened beside the one they were already in, which is the opposite of the shortcut the row is meant to be.
- The choice belongs to the person, not to the platform: there is no correct default here, only a common one.

# Context
- macOS drives Terminal.app through AppleScript in tray/src/mac.rs. Linux tries x-terminal-emulator, gnome-terminal, konsole and xterm in order. Windows routes through the existing WSL-aware command path.
- The companion must not gain a way to run an arbitrary command from a setting: that would hand anyone who can write CDX's state a shell, through a process the user did not start themselves.
- CDX already owns every other durable tray preference — autostart, alerts, plugins — and the companion reads them from the snapshot rather than keeping its own store.

# Acceptance criteria
- AC1: An operator can name a preferred terminal application through CDX, and can unset it to return to the platform default.
- AC2: The preference reaches the companion through the existing snapshot, not through a second store or a companion-side configuration file.
- AC3: A named terminal that is absent, or that fails to start, falls back to the platform default rather than leaving the click doing nothing.
- AC4: A preference cannot express an arbitrary command: what is stored is an application to open a session in, and nothing in it reaches a shell as a command.
- AC5: The macOS, Linux and Windows paths each honour the preference in the way that platform actually launches an application, and each is documented.
- AC6: Focused tests cover the default, a named terminal, an absent one, and the refusal of anything that is not an application name; project validation passes.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_034_the_tray_opens_the_terminal_you_actually_use`
- Architecture decision(s): (none yet)

# References
- tray/src/mac.rs
- tray/src/linux.rs
- tray/src/win.rs
- src/commands/tray.py

# Backlog
- `item_095_add_a_cdx_owned_terminal_preference_the_tray_honours`
