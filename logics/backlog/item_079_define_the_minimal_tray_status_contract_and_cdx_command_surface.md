## item_079_define_the_minimal_tray_status_contract_and_cdx_command_surface - Define the minimal tray status contract and CDX command surface
> From version: 0.17.1
> Schema version: 1.0
> Status: In progress
> Understanding: 100%
> Confidence: 95%
> Progress: 100%
> Complexity: Medium
> Theme: Desktop integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: Define the minimal tray status contract and CDX command surface
- Keywords: scaffolded-backlog, define the minimal tray status contract and cdx command surface, implementation-ready
- Use when: Implementing the scaffolded slice for Define the minimal tray status contract and CDX command surface.
- Skip when: The change belongs to another backlog slice.

# Problem
- The current JSON status is CLI-oriented, so a tray consumer needs a small stable interpretation layer for urgency, freshness, and action states.
- A tray feature must be discoverable and removable without surprising users of the normal CLI.
- A background consumer that probes providers on its own schedule would race codex_auth_lock and can invalidate the user's rotating OAuth refresh token, so the refresh policy belongs in this contract rather than in the native companion.

# Scope
- In:
  - Trace the existing JSON status output and expose only any missing documented fields required by a local tray consumer.
  - Define the cdx tray install, launch, status, and uninstall contracts with non-mutating defaults.
  - Implement one platform-neutral status-to-display-state mapper covering known quota, no sessions, stale data, auth-locked non-refreshable data, and command failure.
  - Define the snapshot as versioned, cache-backed, and read-only: the tray reads it, CDX writes it, and only an explicit menu refresh may request a live probe.
  - Add focused unit tests and concise CLI documentation.
- Out:
  - Writing native tray UI code or adding a mandatory GUI dependency.
  - Changing quota ranking or probing provider APIs outside the existing status pipeline.
  - Adding a second refresh policy, TTL, or provider probe alongside the ones in src/session_status.py.
  - Adding persistent background services or automatic startup.

# Acceptance criteria
- AC1: cdx tray help describes install, launch, status, and uninstall, and ordinary cdx commands remain behaviourally unchanged.
- AC2: The defined local status payload is versioned and cache-backed, and distinguishes fresh, stale, auth-locked, unavailable, and failed states without fabricating usage figures or triggering a live probe on a timer.
- AC3: One tested mapper selects a privacy-preserving icon state from the most urgent eligible session and produces concise per-session menu data.
- AC4: The command contract supports a manual refresh and a terminal-opening action without requiring an always-running daemon, and an explicit refresh reports auth_locked honestly instead of returning a stale value as fresh.
- AC5: A reader that meets an unknown snapshot major version keeps serving the fields it understands and reports one update hint, so no CDX release forces a companion upgrade.
- AC6: Focused tests and the project validation suite pass.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: cdx tray help describes install, launch, status, and uninstall, and ordinary cdx commands remain behaviourally unchanged.
- request-AC2 -> This backlog slice. Proof: AC2: The defined local status payload is versioned and cache-backed, and distinguishes fresh, stale, auth-locked, unavailable, and failed states without fabricating usage figures or triggering a live probe on a timer.
- request-AC3 -> This backlog slice. Proof: AC3: One tested mapper selects a privacy-preserving icon state from the most urgent eligible session and produces concise per-session menu data.
- request-AC4 -> This backlog slice. Proof: AC4: The command contract supports a manual refresh and a terminal-opening action without requiring an always-running daemon, and an explicit refresh reports auth_locked honestly instead of returning a stale value as fresh.
- request-AC10 -> This backlog slice. Proof: AC5: A reader that meets an unknown snapshot major version keeps serving the fields it understands and reports one update hint, so no CDX release forces a companion upgrade.
- request-AC9 -> This backlog slice. Proof: AC6: Focused tests and the project validation suite pass.

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
