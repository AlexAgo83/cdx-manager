## item_081_add_linux_tray_support_and_explicit_release_asset_installation - Add Linux tray support and explicit release-asset installation
> From version: 0.17.1
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 55%
> Complexity: High
> Theme: Distribution
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-10 21:52:54

# AI Context
- Summary: Add Linux tray support and explicit release-asset installation
- Keywords: scaffolded-backlog, add linux tray support and explicit release-asset installation, implementation-ready
- Use when: Implementing the scaffolded slice for Add Linux tray support and explicit release-asset installation.
- Skip when: The change belongs to another backlog slice.

# Problem
- Linux desktop environments vary in system-tray support, and platform-specific companion artifacts need an honest, reversible installation path.
- StatusNotifierItem over D-Bus is the only portable Linux tray protocol, and GNOME implements it only through an extension that Ubuntu ships and a stock GNOME does not, so a distribution list would be wrong on both sides.
- The base CDX package should not embed every native binary or gain tray-only runtime dependencies.
- CDX is installed with pip while the companion is a release asset, so an upgrade of one cannot execute the other; version drift is the normal state, not the exception.

# Scope
- In:
  - Implement Linux support over StatusNotifierItem with ksni so the asset carries no gtk, libxdo, or libayatana-appindicator prerequisite, resolving the org.kde.StatusNotifierWatcher D-Bus name at runtime and reporting a clear unsupported-environment result when it is absent, without matching distribution or desktop names.
  - Build the Linux asset for musl, statically: no glibc version dependency, no C toolchain to produce it, nothing to install to run it. Verified in the managed Ubuntu WSL.
  - Package per-platform, per-architecture companion release assets plus machine-readable checksums, on top of the build and signing capability item_080 established.
  - Implement explicit asset selection, checksum verification, local install-state recording, launch, uninstall, and CDX-managed update paths that keep the companion aligned with the installed CDX release.
  - Document manual distribution, explicit CDX-managed updates, first-launch security prompts, supported platforms, startup opt-in if provided, and recovery steps.
- Out:
  - Universal support for every Linux shell or panel.
  - Package-manager repositories, Flatpak, Snap, Homebrew casks, app stores, signing, notarization, or independent background updates.
  - Silent upgrades or deletion of user data during uninstall.

# Acceptance criteria
- AC1: A Linux environment exposing the StatusNotifierItem watcher renders the core CDX menu, and one without it reports an unsupported environment without a crash or a startup registration. The Linux asset starts on a system with no gtk, libxdo, or appindicator package installed.
- AC2: cdx tray install and the explicit CDX update path choose only the matching OS and architecture release asset, reject a missing or mismatched checksum before use, and keep an installed tray companion aligned with the installed CDX release.
- AC3: cdx tray uninstall removes only files and startup entries previously recorded for the tray companion.
- AC4: A companion whose version differs from the installed CDX keeps serving every snapshot field it understands and reports one update hint, so a pip upgrade of CDX never leaves the user without a working tray.
- AC5: Documentation states the real trust model: the macOS bundle is self-signed and vouched for by the published checksum rather than by Apple, installation happens through cdx tray install so no quarantine attribute is applied, and no browser download link is offered.
- AC6: Focused installer, Linux boundary, and end-to-end command tests plus project validation pass.

# AC Traceability
- request-AC5 -> This backlog slice. Proof: AC1: A Linux environment exposing the StatusNotifierItem watcher renders the core CDX menu, and one without it reports an unsupported environment without a crash or a startup registration.
- request-AC7 -> This backlog slice. Proof: AC2: cdx tray install and the explicit CDX update path choose only the matching OS and architecture release asset, reject a missing or mismatched checksum before use, and keep an installed tray companion aligned with the installed CDX release. AC3: cdx tray uninstall removes only files and startup entries previously recorded for the tray companion.
- request-AC10 -> This backlog slice. Proof: AC4: A companion whose version differs from the installed CDX keeps serving every snapshot field it understands and reports one update hint.
- request-AC8 -> This backlog slice. Proof: AC5: Documentation states the real trust model: self-signed bundle vouched for by the published checksum, installation through cdx tray install with no quarantine attribute, and no browser download link.
- request-AC9 -> This backlog slice. Proof: AC6: Focused installer, Linux boundary, and end-to-end command tests plus project validation pass.

# Decision framing
- Product framing: Not needed
- Architecture framing: Settled in `adr_005_cdx_tray_runtime_and_companion_transport_boundary`

# Links
- Product brief(s): `prod_024_cdx_tray_usage_monitor`
- Architecture decision(s): `adr_005_cdx_tray_runtime_and_companion_transport_boundary`
- Request: `req_035_add_an_optional_cross_platform_cdx_tray_usage_monitor`
- Primary task(s): `task_046_orchestrate_the_optional_cross_platform_cdx_tray_usage_monitor`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
