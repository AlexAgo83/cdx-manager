## req_035_add_an_optional_cross_platform_cdx_tray_usage_monitor - Add an optional cross-platform CDX tray usage monitor
> From version: 0.17.1
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: High
> Theme: Desktop integration
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-10 20:16:59

# AI Context
- Summary: Add an optional cross-platform CDX tray usage monitor
- Keywords: request-chain-scaffold, add an optional cross-platform cdx tray usage monitor, development-ready
- Use when: You need to implement or review the scaffolded workflow for Add an optional cross-platform CDX tray usage monitor.
- Skip when: The change is unrelated to this scaffolded request chain.

# Needs
- CDX already resolves per-session usage through cdx status --json, but users must open a terminal to see remaining capacity and resets.
- A compact, always-available system tray indicator should show the most constrained active CDX session and reveal all session gauges on demand.
- The same feature must work on macOS, native Windows, Linux desktop environments with a system tray, and Windows-hosted WSL installations without making the base CLI depend on the tray runtime.
- The first release must be usable without developer-program accounts, code-signing certificates, app stores, or automatic background installation.

# Context
- src/commands/status.py and the existing cdx status --json contract expose provider-neutral session rows, remaining quota, availability, and reset information that the tray must consume rather than reimplement.
- src/notify.py already distinguishes macOS, Windows, WSL, and Linux notification channels, including the fact that WSL must cross to the Windows host through interop.
- The published package is a Python CLI with only cryptography as a runtime dependency; a tray runtime must be optional so ordinary cdx installation and headless use remain unchanged.
- The product mockups establish the intended interaction: a low-noise CDX status icon, colour signalling based on the most urgent usable quota, and a short session list on click.
- src/session_status.py already caches status per session with per-provider TTLs (60s generic, 300s Codex, 600s Claude) and cdx status --cached reads without probing. A tray must consume that cache rather than add a second refresh policy.
- src/codex_usage.py serializes live quota probes on codex_auth_lock because Codex rotates its OAuth refresh token on refresh. The launcher holds that lock for the whole interactive session, so a live probe during active work returns auth_locked. The tray will therefore display cached values precisely when the user is working, and that state must be shown rather than hidden.
- Linux has no single tray API. StatusNotifierItem over D-Bus is the only portable one, and GNOME implements it only through an extension that Ubuntu ships and a stock GNOME does not, so capability must be resolved at runtime rather than from a distribution list.
- adr_005 fixes the runtime, the snapshot transport, the poll periods, the refresh policy, and the macOS signing identity that this request and its dependants rely on.
- Apple Silicon will not execute unsigned arm64 code, so signing is a build step, not a distribution choice. adr_005 settles it as a self-signed certificate held on the build machine: free, no Apple account, and stable across builds so the macOS notification grant survives a companion update.
- Gatekeeper only inspects files carrying com.apple.quarantine, and that attribute is set by the downloading application rather than by the file itself. Because cdx tray install fetches the asset directly, no quarantine is applied and no first-launch security prompt appears. This makes the install path load-bearing: a browser download link would reintroduce the block.
- Windows WSL cannot own a Windows notification-area icon from inside Linux. The host executable must query the configured WSL distribution through wsl.exe or consume an explicit host-readable status command.
  - Initial distribution may use release assets and manual first-launch confirmation. Signing, notarization, app-store publication, background tray self-update, telemetry, and account login are deliberately deferred; a tray component updates only as part of an explicit CDX update.

# Acceptance criteria
- AC1: cdx offers an explicit tray command family with install, launch, status, and uninstall operations; invoking cdx alone never installs a tray component, registers startup, or changes desktop settings.
- AC2: The tray consumes the documented cdx status --json output through the existing session cache, never forces a live provider probe on its own schedule, and shows a clear unavailable, stale, not-refreshable-while-a-session-runs, or error state instead of inventing quota values when a refresh fails.
- AC3: The active tray icon communicates the most urgent relevant usage state without exposing account names or quota details until the user opens its menu.
- AC4: Opening the tray menu shows each enabled CDX session with provider, concise remaining-usage gauge, freshness/reset information when known, and actions to refresh and open the relevant terminal command.
- AC5: macOS, native Windows, and supported Linux tray environments provide the same core status and menu behaviour from native host processes, with Linux capability resolved at runtime through the StatusNotifierItem D-Bus name rather than a distribution or desktop-name list.
- AC6: On Windows with CDX installed in WSL, the Windows-hosted tray component reads status through WSL interop, reports unavailable interop or missing CDX honestly, and does not require a Linux GUI server.
- AC7: Installation and explicit CDX update select only the matching OS and architecture release asset, verify its published checksum before use, keep an installed tray companion aligned with the installed CDX release, record only the local state needed for uninstall including the Windows Start Menu shortcut that toasts require, complete without administrator rights, and leave the base cdx runtime free of tray-only dependencies.
- AC8: The initial distribution and documentation describe installation through cdx tray install, explicit CDX-managed tray updates, and the actual trust model truthfully: the macOS companion is a self-signed bundle whose integrity is guaranteed by the published checksum rather than by Apple, and it is never offered as a browser download because that would quarantine it. They do not claim Developer ID signing, notarization, store distribution, background self-update, or universal Linux desktop support.
- AC9: Focused automated checks cover quota-state mapping, JSON/error/staleness handling, install-target selection and checksum rejection, snapshot-version compatibility, poll and back-off behaviour, and WSL command construction; platform integration checks and project validation pass.
- AC10: The tray reads a versioned snapshot from cdx tray status --json on a bounded schedule: at most every 30 seconds natively and every 60 seconds across the Windows-to-WSL boundary, stopping when no session is enabled and backing off after repeated read failures so a WSL distribution is not woken indefinitely. A companion that meets an unknown snapshot major version keeps serving every field it understands and surfaces one update hint instead of failing, so CDX and the companion never require lockstep versions.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_024_cdx_tray_usage_monitor`
- Architecture decision(s): `adr_005_cdx_tray_runtime_and_companion_transport_boundary`

# References
- README.md
- pyproject.toml
- src/cli.py
- src/cli_args.py
- src/commands/status.py
- src/codex_usage.py
- src/session_status.py
- src/status_view.py
- src/notify.py
- logics/architecture/adr_005_cdx_tray_runtime_and_companion_transport_boundary.md
- logics/external/cdx-tray-mockup-macos.png
- logics/external/cdx-tray-mockup-windows-wsl.png
- logics/external/cdx-tray-mockup-linux.png

# Backlog
- `item_079_define_the_minimal_tray_status_contract_and_cdx_command_surface`
- `item_080_build_native_tray_companions_for_macos_and_windows_plus_wsl`
- `item_081_add_linux_tray_support_and_explicit_release_asset_installation`
