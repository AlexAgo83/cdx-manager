## req_053_bring_back_the_terminal_an_alert_came_from - Bring back the terminal an alert came from
> From version: 0.18.6
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: High
> Theme: tray-companion
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: An alert names which session needs attention and leaves the operator to find its window among many. A hook has no tty, but the terminal's own session identifier survives in the environment it inherits — verified on macOS, where iTerm2 answers to exactly that UUID. Coverage is per terminal and per platform, and honest about where no mechanism exists.
- Keywords: alerts, focus, terminal, iterm, applescript, notification, spool, privacy
- Use when: Working on what an agent alert carries, on what clicking an alert or a banner does, or on how the companion reaches the terminal a session runs in.
- Skip when: Working on which terminal a tray session row opens for a new window, on alert delivery and muting, or on the quota rows the menu shows.

# Needs
- Return to the terminal an agent alert came from by clicking the alert, instead of hunting for the window among many open sessions.
- Get the same behaviour from the notification banner where the platform allows it.
- Never be sent to the wrong window when the original one is gone.

# Context
- The case this is for is several sessions running in parallel: the alert already names which one, and the operator still has to find its window by hand.
- A hook has no controlling terminal — every descriptor is a pipe — so identification has to come from the environment the provider inherited at launch.
- On macOS the environment carries a usable key: ITERM_SESSION_ID's UUID is the session id iTerm2 answers to in AppleScript, verified against a live window.
- Terminal.app exposes tab tty rather than a matching identifier, and Ghostty, kitty and WezTerm each have their own remote control, so coverage is per terminal and not a single mechanism.
- Windows can at best raise the console window, never a Windows Terminal tab, and the OS routinely answers a background app's focus request by flashing the taskbar instead.
- Wayland forbids a client raising another by design, so Linux coverage stops at X11.
- Clicking a tray row and clicking a notification banner are different problems: the companion is already the clicked application in the first case, while the second needs a notification delegate that does not exist yet, and on Windows a COM activator that is impractical for a non-packaged app.
- Terminal identity is CDX-level metadata rather than conversation content, so it fits the spool's privacy rule, but adding it is a deliberate extension of what structured_details allows to cross.

# Acceptance criteria
- AC1: A hook records which terminal its session runs in, from the environment, and the alert carries that identity to the tray.
- AC2: Clicking a tray alert row focuses the terminal session the alert came from, on a platform and terminal where a documented mechanism exists.
- AC3: An alert whose target no longer exists does nothing visible when clicked, and never focuses a different window.
- AC4: An alert with no usable identity, or on a platform with no mechanism, renders its focus action as unavailable with the reason rather than silently doing nothing.
- AC5: Where the platform permits it, clicking the notification banner does what clicking the tray row does.
- AC6: The identity crossing into the spool is named metadata only, documented in structured_details alongside what still may not cross.
- AC7: A companion older than this delivery ignores the added fields and behaves exactly as before.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_040_alerts_that_lead_back_to_their_terminal`
- Architecture decision(s): (none yet)

# References
- User request: clicking a tray alert, or the notification itself, should focus the terminal that produced it
- Verified on macOS: a hook has no tty on any descriptor (providers spawn it with pipes), so the terminal cannot be identified that way
- Verified on macOS: ITERM_SESSION_ID is inherited by the hook and its UUID matches the session id iTerm2 exposes through AppleScript
- src/agent_notify.py:185 structured_details declares exactly what may cross into the spool, and why everything else does not
- tray/src/menu.rs Availability::Unavailable exists, is documented as awaiting its first real user, and is what an action without a mechanism should render as
- tray/src/notify.rs: no UNUserNotificationCenter delegate is set, so notification clicks are not received at all today
- tray/src/win.rs and tray/src/linux.rs: Windows Terminal exposes no tab activation API, and Wayland forbids one client raising another

# Backlog
- `item_104_record_which_terminal_a_hook_fired_from_and_carry_it_to_the_tray`
- `item_105_focus_the_originating_terminal_from_a_tray_alert_row`
- `item_106_make_the_notification_banner_act_like_the_alert_row_on_macos`
