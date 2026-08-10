## item_080_build_native_tray_companions_for_macos_and_windows_plus_wsl - Build native tray companions for macOS and Windows plus WSL
> From version: 0.17.1
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: High
> Theme: Desktop integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: Build native tray companions for macOS and Windows plus WSL
- Keywords: scaffolded-backlog, build native tray companions for macos and windows plus wsl, implementation-ready
- Use when: Implementing the scaffolded slice for Build native tray companions for macOS and Windows plus WSL.
- Skip when: The change belongs to another backlog slice.

# Problem
- A Python CLI cannot place an icon in macOS or Windows system UI by itself.
- Windows-hosted WSL needs a host-side application and a robust bridge to the WSL CDX executable.
- Each wsl.exe call costs roughly 100-300 ms and keeps the WSL VM alive, so an unbounded poll loop turns a status icon into a permanent background cost.

# Scope
- In:
  - Stand up the minimum build capability this slice needs to be testable at all: a Rust toolchain, the per-platform target matrix, the macOS bundle layout, and the self-signed signing step from adr_005. Release-asset packaging, checksums, and the installer stay in item_081.
  - Build the companion on the runtime settled in adr_005 (tray-icon plus muda on macOS and Windows, ksni on Linux, no webview) and package it as a separate artifact.
  - Implement the shared menu, bounded periodic refresh, manual refresh, error rendering, and clean quit behaviour for macOS and Windows.
  - Honour the adr_005 poll budget: at most every 30 seconds natively and 60 seconds across the WSL boundary, no polling when no session is enabled, and a back-off after repeated read failures so the WSL VM is not kept awake.
  - Implement Windows discovery/configuration for native CDX and one configured WSL target using wsl.exe, with clear errors for missing interop or executable.
  - Package the macOS companion as a CDX.app bundle with LSUIElement set, a stable bundle identifier, and the CDX icon, signed at build time with the self-signed identity from adr_005 rather than ad-hoc.
  - Register the Windows AppUserModelID during cdx tray install and create the per-user Start Menu shortcut that carries it plus a stub CLSID, without which a toast is silently dropped; record both so uninstall removes them, and require no administrator rights.
  - Use the supplied CDX icon assets at appropriate native sizes and add focused platform-boundary tests where executable UI testing is impractical.
- Out:
  - Developer ID signing, notarization, Microsoft Store publishing, auto-update, or Windows service installation.
- Any browser-download or .dmg distribution path for macOS, which would quarantine the bundle and reintroduce a Gatekeeper block.
  - Multiple WSL distribution aggregation, remote machines, or GUI operation within WSL.
  - A full desktop dashboard or account-management UI.

# Acceptance criteria
- AC1: macOS and Windows artifacts display the same core usage states and session menu from the shared local status contract.
- AC2: A Windows host can obtain status from a configured WSL CDX command without requiring an X server, and failures identify the unavailable boundary.
- AC3: The closed icon carries no account, session, or quota detail, and the open menu lists each enabled session with provider, remaining-usage gauge, freshness or reset when known, refresh, a terminal action, and quit.
- AC4: The bundled icon assets render correctly at the required tray sizes.
- AC5: Polling stays inside the adr_005 budget, stops when no session is enabled, and backs off after repeated failures, verified on the Windows-to-WSL path.
- AC6: Targeted tests and documented manual smoke checks pass on the supported host platforms.

# AC Traceability
- request-AC5 -> This backlog slice. Proof: AC1: macOS and Windows artifacts display the same core usage states and session menu from the shared local status contract.
- request-AC6 -> This backlog slice. Proof: AC2: A Windows host can obtain status from a configured WSL CDX command without requiring an X server, and failures identify the unavailable boundary.
- request-AC3 -> This backlog slice. Proof: AC3: The closed icon carries no account, session, or quota detail.
- request-AC4 -> This backlog slice. Proof: AC3: The open menu lists each enabled session with provider, remaining-usage gauge, freshness or reset when known, refresh, a terminal action, and quit.
- request-AC10 -> This backlog slice. Proof: AC5: Polling stays inside the adr_005 budget, stops when no session is enabled, and backs off after repeated failures, verified on the Windows-to-WSL path.
- request-AC9 -> This backlog slice. Proof: AC6: Targeted tests and documented manual smoke checks pass on the supported host platforms.

# Decision framing
- Product framing: Not needed
- Architecture framing: Settled in `adr_005_cdx_tray_runtime_and_companion_transport_boundary`

# Links
- Product brief(s): `prod_024_cdx_tray_usage_monitor`
- Architecture decision(s): `adr_005_cdx_tray_runtime_and_companion_transport_boundary`
- Request: `req_035_add_an_optional_cross_platform_cdx_tray_usage_monitor`
- Primary task(s): `task_046_orchestrate_the_optional_cross_platform_cdx_tray_usage_monitor`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
