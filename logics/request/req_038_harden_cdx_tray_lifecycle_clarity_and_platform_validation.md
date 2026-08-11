## req_038_harden_cdx_tray_lifecycle_clarity_and_platform_validation - Harden CDX tray lifecycle, clarity, and platform validation
> From version: 0.17.1
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Complexity: High
> Theme: Desktop integration
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-11 04:17:45

# AI Context
- Summary: Harden CDX tray lifecycle, clarity, and platform validation
- Keywords: request-chain-scaffold, harden cdx tray lifecycle, clarity, and platform validation, development-ready
- Use when: You need to implement or review the scaffolded workflow for Harden CDX tray lifecycle, clarity, and platform validation.
- Skip when: The change is unrelated to this scaffolded request chain.

# Needs
- The tray must be quiet, transparent, and recoverable on a personal desktop: explicit startup control, one instance, useful diagnostics, and safe updates are more valuable than hidden background machinery.
- Windows-hosted WSL needs a deterministic default-distribution path plus an explicit override, while Linux support must describe only desktop environments that have been tested.
- A small icon must communicate actionable CDX availability without misleading averages, colour-only meaning, or revealing session and task details while closed.
- Native behaviour must be validated on real managed macOS and Windows plus WSL machines in addition to deterministic local tests.

# Context
- The base tray companion request req_035 owns installation, status, and the native menu. Alert delivery and the Logics card are separate dependent requests and must retain their bounded event and plugin contracts.
- This request is a release gate rather than a later polish pass. Single-instance ownership, explicit startup control, and cdx tray doctor are the difference between a companion that can be shipped and one that duplicates its icon with no way to diagnose it, so no tray release ships from req_035 alone.
- Linux tray capability is resolved at runtime through the StatusNotifierItem D-Bus watcher, because GNOME provides it only through an extension that Ubuntu ships and a stock GNOME does not; a documented tested matrix records what was verified, not what is detected.
- The chosen operating policy is manual launch by default; cdx tray autostart on and off are explicit opt-in controls. The installed companion must not create a startup entry merely because cdx tray install ran.
- A single user-level tray instance owns the icon. A second launch reports the existing instance; cdx tray doctor reports instance, startup, status freshness, installed version, and supported desktop capability.
- Windows starts from the default WSL distribution, with cdx tray configure wsl --distro NAME as an explicit override. V1 never aggregates several distributions.
- The closed icon represents the most constrained currently usable CDX capacity, never an average. Its tooltip states the capacity state in words, the remaining figure, the reset when known, and an explicit unknown state — but not the session name. This resolves a conflict with req_035 AC3, which forbids exposing accounts before the menu is opened: a tooltip appears on hover with no click and shows up in a screen share, so the name stays one click away in the menu while everything else is said. Menu text and symbols carry every state that colour also conveys.
- Native notifications retain system Focus and Do Not Disturb behaviour, use no urgent interruption mode, and quota urgency remains an icon state rather than a new toast category.
- Tray updates remain explicit CDX-managed updates. Installation stages a verified replacement, starts it successfully, then retires the old companion; failure leaves the prior working version available.
- The managed validation matrix is the current arm64 macOS host and a managed Windows host with an Ubuntu WSL distribution. Tests are read-only except for scoped install and uninstall fixtures, which must be cleaned up.

# Acceptance criteria
- AC1 (revised 2026-08-11, at the product owner's decision): cdx tray install starts the companion it just installed, and offers startup rather than adding it silently — interactively it asks, non-interactively it declines and names the command. The original wording forbade startup outright; the reason behind it was that an install must not quietly add a login item, and a confirmation keeps that reason while dropping the friction of a second command. `--yes` and `--no-autostart` answer it without a prompt. The rest stands: cdx tray autostart on and off are explicit, idempotent, user-level operations that report the actual platform state, implemented as one recorded artifact per platform (a LaunchAgent plist, the per-user Run key, or an XDG autostart entry) that off deletes, and requiring no administrator rights.
- AC2: Only one tray instance owns a user session; duplicate launch, crash recovery, quit, and cdx tray doctor provide clear bounded diagnostics without a persistent background service.
- AC3: Windows uses the default WSL distribution unless an explicit named override is configured, reports a missing or invalid override honestly, and does not aggregate distributions in v1.
- AC4: The tray state selects the most constrained usable capacity, names its source and reset in the tooltip/menu, renders an explicit unknown state, and never makes colour the sole state signal.
- AC5: Completion and attention alerts respect native notification settings; quota state produces no new toast, and no tray surface exposes session, repository, task, or preview details while closed.
- AC6: cdx-managed update verifies the matching asset before staging, preserves the prior working companion until replacement starts, and cdx tray doctor explains partial installation or version mismatch recovery.
- AC7: Linux support is limited to a documented tested desktop matrix, while tray capability is detected at runtime through the StatusNotifierItem watcher and an unsupported environment is reported without startup registration or a crash.
- AC8: Automated boundary tests cover lifecycle controls, single-instance handling, WSL selection, quota-state mapping, privacy, accessibility labels, update recovery, and unsupported Linux capability; manual smoke validation passes on the managed arm64 macOS host and managed Windows plus Ubuntu WSL host.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_027_trustworthy_cdx_tray_operation`
- Architecture decision(s): `adr_005_cdx_tray_runtime_and_companion_transport_boundary`

# References
- README.md
- src/notify.py
- src/commands/maintenance.py
- src/update_check.py
- logics/request/req_035_add_an_optional_cross_platform_cdx_tray_usage_monitor.md
- logics/request/req_036_route_cdx_agent_alerts_through_an_active_tray_companion.md
- logics/request/req_037_add_a_first_party_logics_plugin_surface_to_the_cdx_tray.md

# Backlog
- `item_084_add_explicit_cdx_tray_lifecycle_capacity_privacy_and_recovery_controls`
- `item_085_constrain_wsl_and_linux_tray_support_and_validate_it_on_real_hosts`
