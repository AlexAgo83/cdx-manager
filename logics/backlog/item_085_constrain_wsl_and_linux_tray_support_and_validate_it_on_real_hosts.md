## item_085_constrain_wsl_and_linux_tray_support_and_validate_it_on_real_hosts - Constrain WSL and Linux tray support and validate it on real hosts
> From version: 0.17.1
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 90%
> Progress: 95%
> Complexity: Medium
> Theme: Platform support
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-10 22:38:25

# AI Context
- Summary: Constrain WSL and Linux tray support and validate it on real hosts
- Keywords: scaffolded-backlog, constrain wsl and linux tray support and validate it on real hosts, implementation-ready
- Use when: Implementing the scaffolded slice for Constrain WSL and Linux tray support and validate it on real hosts.
- Skip when: The change belongs to another backlog slice.

# Problem
- WSL and Linux tray assumptions vary by distribution and desktop environment, so broad claims without a configuration path and hardware smoke tests are unreliable.
- First hardware figures, from kdesktop: the bare wsl.exe crossing costs 132 ms, a full cdx tick 344 ms, and the companion's own end-to-end tick 285-320 ms, all warm. Recorded in adr_005; the remaining unknown is the cold-start cost when the distribution has been idle.

# Smoke validation record
- Runner: `scripts/tray-smoke.sh`, driven by `CDX_TRAY_BIN`. Read-only apart from starting and stopping the companion; it writes nothing outside the companion's own runtime directory.
- kdesktop, Windows companion serving CDX through Ubuntu WSL, 2026-08-10: 6 of 6 checks pass. Menu `CDX · critical · 11 session(s)` on the real fleet, poll period 60 s across WSL, poll cost 387-401 ms over three samples, so worst-case alert latency <= 61 s. A second companion exits 3 and names the holding pid; a companion started over a dead pid's lock reclaims it.
- The same runner on macOS arm64, native transport, 6 of 6: poll cost 83-85 ms, and the empty-fleet branch shows polling stopped with no enabled session. The two hosts together cover both branches of the polling rule, because whether a fleet is populated is a property of the host and not of the code.
- The poll cost is sampled three times rather than once: the first sample pays for a cold WSL VM, and reporting only that would overstate the steady-state cost that the 60 s period has to afford.
- The runner asks the companion for its lock path via `cdx-tray --lock-path` instead of recomputing it. The rule is TMPDIR on macOS and Linux but LOCALAPPDATA on Windows, so a script that reimplemented it would look in the wrong place on the one platform this check exists for.
- Absent-watcher path, verified on kdesktop's Ubuntu WSL: the session bus answers `ListNames` with rc 0 and four names, and `org.kde.StatusNotifierWatcher` is not among them. The backend shells out to the same `dbus-send` call, so this host takes the "this desktop has no system tray" branch rather than the cruder "no D-Bus session bus" one. That is the interesting half of AC2: a session bus that exists and simply has no watcher is what a headless or GNOME-without-AppIndicator desktop looks like, and it must be reported rather than crashed on.
- The Linux binary itself is not yet run on that host: WSL Ubuntu has no Rust toolchain, and installing one is a footprint change on a machine that belongs to someone. The watcher decision is verified there through the identical D-Bus query, and the branch it feeds is covered by the Rust tests; running the built binary on a real Linux desktop remains open.
- Not yet verifiable, with the reason rather than a silent gap: the toast reaching Action Center through the installed Start Menu shortcut needs a notification to exist, which is `task_047`; the Zone.Identifier stream on a fetched asset needs `cdx tray install` to fetch a release asset, which is `item_081`. AC3 is therefore met for the two measurements and the polling rule, and blocked on those two slices for the rest.

# Scope
- In:
  - Implement default and explicitly selected WSL distribution resolution with truthful diagnostics.
  - Detect Linux tray capability at runtime by resolving the org.kde.StatusNotifierWatcher D-Bus name, define the unsupported behaviour, and record the desktops actually verified rather than inferring support from a distribution name.
  - Run documented smoke checks on managed Windows plus Ubuntu WSL and record the results.
- Out:
  - Multiple-distribution aggregation, WSL GUI, network relays, universal Linux support, or production changes to managed hosts.

# Acceptance criteria
- AC1: Default and configured WSL distribution selection are deterministic and diagnose bad configuration. A configured name that is not installed is named as such, with the installed distributions listed, and never silently falls back to the default.
- AC2: Linux tray capability is resolved at runtime through the StatusNotifierItem watcher, an absent watcher is reported safely, and the verified desktops are documented as tested rather than as supported by name.
- AC3: The managed Windows plus Ubuntu WSL smoke run measures the observed alert latency and the wsl.exe poll cost, confirms the tray stops polling when no session is enabled, verifies that a toast reaches Action Center through the installed Start Menu shortcut, and records whether the fetched asset carries a Zone.Identifier stream.
- AC4: Automated checks and the managed Windows plus Ubuntu WSL smoke validation pass.

# AC Traceability
- request-AC3 -> This backlog slice. Proof: AC1: Default and configured WSL distribution selection are deterministic and diagnose bad configuration.
- request-AC7 -> This backlog slice. Proof: AC2: Linux tray capability is resolved at runtime through the StatusNotifierItem watcher, an absent watcher is reported safely, and the verified desktops are documented as tested.
- request-AC8 -> This backlog slice. Proof: AC3: The managed smoke run measures observed alert latency and wsl.exe poll cost. AC4: Automated checks and the managed Windows plus Ubuntu WSL smoke validation pass.

# Decision framing
- Product framing: Not needed
- Architecture framing: Settled in `adr_005_cdx_tray_runtime_and_companion_transport_boundary`

# Links
- Product brief(s): `prod_027_trustworthy_cdx_tray_operation`
- Architecture decision(s): `adr_005_cdx_tray_runtime_and_companion_transport_boundary`
- Request: `req_038_harden_cdx_tray_lifecycle_clarity_and_platform_validation`
- Primary task(s): `task_049_orchestrate_trustworthy_cdx_tray_operation_and_platform_validation`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
