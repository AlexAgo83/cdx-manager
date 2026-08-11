## req_042_synchronize_cdx_tray_alert_badges_with_menu_reading - Synchronize CDX tray alert badges with menu reading
> From version: 0.18.4
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Tray usability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: Synchronize CDX tray alert badges with menu reading
- Keywords: request-chain-scaffold, synchronize cdx tray alert badges with menu reading, development-ready
- Use when: You need to implement or review the scaffolded workflow for Synchronize CDX tray alert badges with menu reading.
- Skip when: The change is unrelated to this scaffolded request chain.

# Needs
- The tray's temporary +N marker, native notification delivery, spool acknowledgement, and Recent alerts menu history currently have independent lifetimes, so they do not communicate one coherent unread state.
- Opening the tray is the user's explicit reading action. It should clear the unread badge and make the alerts visible in that consultation disappear before the next consultation.
- A native operating-system notification must not count as read because it can be missed; an alert arriving while the tray menu is open must remain unread for the next consultation.

# Context
- A tray event is currently acknowledged to CDX after it has been drawn and delivered, which is the correct delivery guarantee but is not a user-read signal.
- tray/src/hint.rs shows a count marker for 45 seconds based on freshly collected events. tray/src/runner.rs retains a bounded in-memory history for the companion lifetime, and menu.rs displays it on every later menu build.
- macOS, Windows, and Linux have different native menu loops. The implementation must use each backend's actual menu-open and menu-close lifecycle signals, but expose one identical read-state behavior rather than relying on a timeout or a platform-specific click convention.
- The event spool remains the delivery and crash-recovery boundary. Read state is local volatile tray UI state only; it must not alter acknowledgement, replay safety, event persistence, or the existing bounded spool behavior.

# Acceptance criteria
- AC1: The tray has one explicit unread-alert state. An incoming alert adds one unread item, shows its marker, and makes it available in the current unread-alert menu section.
- AC2: Opening the tray menu marks the alerts already visible in that consultation as read and clears the badge immediately. Those alerts remain visible for that open menu, then are absent on the next menu opening.
- AC3: An alert that arrives after the menu opens remains unread, retains or raises the badge, and appears on the next consultation rather than being accidentally cleared with older alerts.
- AC4: Native OS-toast delivery and spool acknowledgement do not mark an alert read. Existing crash replay, idempotent acknowledgement, bounded history, mute behavior, and direct fallback semantics remain unchanged.
- AC5: macOS, Windows, and supported Linux provide the same read-state result through their native menu lifecycle; unavailable or unexpected menu lifecycle events fail safe by retaining alerts rather than silently discarding them.
- AC6: Focused Rust tests cover initial unread count, opening and closing a menu, post-open arrival, repeated opening, badge clearing, history clearing, and preservation of spool acknowledgement behavior.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_031_coherent_cdx_tray_unread_alerts`
- Architecture decision(s): (none yet)

# References
- src/tray_events.py
- tray/src/events.rs
- tray/src/hint.rs
- tray/src/runner.rs
- tray/src/menu.rs
- tray/src/mac.rs
- tray/src/win.rs
- tray/src/linux.rs
- tray/src/backend.rs
- test/test_tray_events_py.py
- tray/Cargo.toml

# Backlog
- `item_089_unify_tray_alert_marker_and_recent_alert_read_state`
