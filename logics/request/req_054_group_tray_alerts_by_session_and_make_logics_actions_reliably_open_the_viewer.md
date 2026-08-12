## req_054_group_tray_alerts_by_session_and_make_logics_actions_reliably_open_the_viewer - Group tray alerts by session and make Logics actions reliably open the viewer
> From version: 0.18.6
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Tray usability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-13 00:53:55

# AI Context
- Summary: Preserve the current bounded unread state, but present it as session groups and make Logics recovery actions launch the correct supported viewer without blocking the native menu.
- Keywords: group, tray, alerts, session, logics, actions, reliably, open, viewer
- Use when: Implementing or reviewing the tray alert grouping and Logics viewer action repair on macOS, native, or WSL paths.
- Skip when: Changing provider alert payloads, building a Logics viewer, or adding a persistent notification archive.

# Needs
- Unread tray alerts are currently rendered as one flat list, so messages from parallel sessions are interleaved instead of being readable in their session context.
- The Logics card declares focused-row and Open Logics actions, but the tray invokes them synchronously, without asking the viewer to open a browser, and without retaining the repository that supplied a focused row. On macOS this presents as a click that does nothing or leaves the tray blocked.
- The upcoming Logics viewer provides a shared Fleet entry point. CDX should use that supported viewer contract rather than create a second server or embed a browser.

# Context
- Structured tray events already carry an optional stable session name. Events without it must remain visible without guessing a target from display text.
- The current unread lifecycle is intentionally consultation-based: opening the tray reads the alerts rendered in that menu while alerts arriving later remain unread. Grouping changes the presentation only; it must not create a second read state.
- The Logics adapter derives status from active session repository roots and currently prefixes rows with a repository basename, but its action contract retains only an action string. A focused action therefore lacks the root required to launch a project-focused viewer reliably.
- logics-manager view --fleet --open is the global Fleet entry point. A focused project action must launch detached from the tray with --focus and --open in the originating repository, allowing Logics to reuse its own viewer server.

# Acceptance criteria
- AC1: The tray presents unread alerts as a bounded Alert groups section: one submenu per structured session, ordered by each group's newest alert, with the session name and count; each submenu contains that session's messages newest first.
- AC2: Alerts without a structured session remain visible in one clearly labelled fallback group and never infer an action target from title or message text.
- AC3: Grouping preserves the existing global history bound, native notification delivery, spool acknowledgement, mute behaviour, direct fallback, and consultation-based unread semantics; an alert arriving after a menu opens remains unread for the next consultation.
- AC4: Selecting a session-bound alert still routes only through the existing stable session action; a malformed or unknown session is harmless and cannot select a different session.
- AC5: Open Logics launches the supported Fleet viewer asynchronously with an explicit browser-open request, so the native tray event loop never waits for a long-running viewer server.
- AC6: Selecting a focused Logics row launches the supported viewer asynchronously with --focus and --open from the exact repository that produced that row; cards spanning repositories never focus a reference in another repository.
- AC7: The plugin snapshot and action boundary carry only the minimum validated repository context needed for the focused launch. Full paths do not appear in alert payloads, tray labels, or arbitrary plugin-defined commands.
- AC8: Focused Python and Rust checks cover grouping and fallback alerts, preserved unread behaviour, detached global and focused viewer argv/cwd routing, rejection of malformed context, and the macOS action path; project and Logics validation pass.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_041_contextual_cdx_tray_recovery_paths`
- Architecture decision(s): (none yet)

# References
- src/tray_logics.py
- src/tray_plugin_actions.py
- src/logics_view.py
- src/commands/tray.py
- src/tray_events.py
- tray/src/events.rs
- tray/src/menu.rs
- tray/src/runner.rs
- tray/src/mac.rs
- logics/request/req_042_synchronize_cdx_tray_alert_badges_with_menu_reading.md
- logics/request/req_048_give_the_logics_tray_card_a_repository_to_report_on.md

# Backlog
- `item_107_group_unread_tray_alerts_by_their_originating_session`
- `item_108_launch_the_correct_logics_fleet_or_project_viewer_from_tray_actions`
