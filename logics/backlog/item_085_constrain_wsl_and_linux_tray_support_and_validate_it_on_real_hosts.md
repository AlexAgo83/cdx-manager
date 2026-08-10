## item_085_constrain_wsl_and_linux_tray_support_and_validate_it_on_real_hosts - Constrain WSL and Linux tray support and validate it on real hosts
> From version: 0.17.1
> Schema version: 1.0
> Status: In progress
> Understanding: 92%
> Confidence: 95%
> Progress: 99%
> Complexity: Medium
> Theme: Platform support
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-10 23:20:18

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
- kdesktop, Windows companion serving CDX through Ubuntu WSL, 2026-08-10: 6 of 6 checks pass. Menu `CDX · critical · 11 session(s)` on the real fleet, poll period 60 s across WSL, poll cost 371-401 ms over three samples across two runs, so worst-case alert latency <= 61 s. A second companion exits 3 and names the holding pid; a companion started over a dead pid's lock reclaims it.
- The same runner on macOS arm64, native transport, 6 of 6: poll cost 88-92 ms, and the empty-fleet branch shows polling stopped with no enabled session. The two hosts together cover both branches of the polling rule, because whether a fleet is populated is a property of the host and not of the code.
- The poll cost is sampled three times rather than once: the first sample pays for a cold WSL VM, and reporting only that would overstate the steady-state cost that the 60 s period has to afford.
- The runner asks the companion for its lock path via `cdx-tray --lock-path` instead of recomputing it. The rule is TMPDIR on macOS and Linux but LOCALAPPDATA on Windows, so a script that reimplemented it would look in the wrong place on the one platform this check exists for.
- kdesktop, Linux companion running natively in Ubuntu 26.04 WSL, 2026-08-10: 5 pass, 1 skipped, 0 fail. Same fleet at `CDX · critical · 11 session(s)`, native period 30 s, poll cost 140-145 ms so alert latency <= 31 s. This is the run that exercises the native-30s branch, which neither of the other two hosts reaches.
- Absent-watcher path, verified there with the real binary: `cdx-tray` exits 1 with `no org.kde.StatusNotifierWatcher on the session bus: this desktop has no system tray. On GNOME, install the AppIndicator extension.` The session bus answers `ListNames` with four names and no watcher among them, so the host takes that branch rather than the cruder "no D-Bus session bus" one. That is the half of AC2 worth having: a bus that exists and simply has no watcher is what a headless session or GNOME-without-AppIndicator looks like, and it must be named rather than crashed on.
- The single-instance check is skipped rather than failed on that host, and the runner says why. Where no backend can draw, the first companion exits before a second can collide with it, so the check has nothing to ask. Counting a skip as a pass would report green for behaviour never exercised; counting it as a failure would cry wolf about the one machine behaving correctly. The tally prints passed, failed and skipped separately.
- The lock is still taken before the backend runs, which is why the reclaim check remains meaningful on that host: the companion took over the dead pid's lock on its way to discovering it had nowhere to draw.
- Built for that host without touching it: a static `x86_64-unknown-linux-musl` binary cross-compiled from macOS through `rust-lld`, because the WSL distribution has no C toolchain and installing one needs a password that must never be handled here. ksni and zbus are pure Rust, so the asset carries no C library — the property `adr_005` asked for, now demonstrated rather than assumed. The recipe is `scripts/build-tray.sh --linux` rather than a note, so `item_081` inherits a reproducible Linux asset instead of a story about one.
- Zone.Identifier, measured on kdesktop rather than deferred: the installer's fetch path is `urllib.request.urlopen` into a file, and a file fetched that way to an NTFS path carries **no** `Zone.Identifier` stream. `Get-Item -Stream *` reports only `:$DATA`. A `Invoke-WebRequest` download to the same directory behaves the same, and a witness file written with an explicit `Zone.Identifier` does show the stream, so the absence is a property of the fetch and not of the detection.
- That matters because the mark of the web is what would put SmartScreen between the user and a companion CDX just installed on their behalf, which is the Windows counterpart of the macOS quarantine attribute `adr_005` relies on being absent. It also means the answer must be re-measured if the fetch ever moves to a mechanism that goes through the Attachment Manager.
- Still blocked, with the reason rather than a silent gap: the toast reaching Action Center through the installed Start Menu shortcut needs a notification to exist, which is `task_047`. Every other AC3 clause is now measured.

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
