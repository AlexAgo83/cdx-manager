## item_082_deliver_agent_hook_events_through_the_active_cdx_tray_with_safe_fallback - Deliver agent hook events through the active CDX tray with safe fallback
> From version: 0.17.1
> Schema version: 1.0
> Status: In progress
> Understanding: 95%
> Confidence: 92%
> Progress: 90%
> Complexity: High
> Theme: Desktop integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-11 00:19:07

# AI Context
- Summary: Deliver agent hook events through the active CDX tray with safe fallback
- Keywords: scaffolded-backlog, deliver agent hook events through the active cdx tray with safe fallback, implementation-ready
- Use when: Implementing the scaffolded slice for Deliver agent hook events through the active CDX tray with safe fallback.
- Skip when: The change belongs to another backlog slice.

# Problem
- Direct hook notifications and an active tray would otherwise create duplicate toasts and leave no durable in-tray signal.
- A cross-process notification handoff must remain best-effort: a provider hook cannot wait on a GUI, and WSL networking cannot be assumed symmetric.
- A polled spool trades latency for portability, and an unbounded poll across wsl.exe keeps the WSL VM permanently awake, so both the delay and the idle cost need explicit limits.

# Scope
- In:
  - Add a small versioned local event-spool and heartbeat protocol beneath the existing composed-notification boundary.
  - Have cdx notify choose tray publication only for a fresh compatible heartbeat, otherwise retain the existing direct notification dispatch unchanged.
  - Have the installed tray consume and acknowledge events once, show a temporary icon hint plus a bounded menu history, and emit one native local notification when its capability is available.
  - Create the Windows Start Menu shortcut carrying the AppUserModelID and its stub CLSID, and register the AUMID. Moved here from item_080 on purpose: its only function is to make a toast reach Action Center, so building it before there is a toast would be work nobody could verify. It lands with the first notification, where it either works or does not.
    - Partly delivered ahead of this slice, under `item_084`, because `cdx tray doctor` had to report the shortcut and reporting a thing nothing creates is a diagnostic that can only ever say "blocked". What exists: `cdx tray install` writes the Start Menu shortcut with the `com.cdx.tray` AppUserModelID, verified on kdesktop by reading the identifier back. What this slice still owns, and what the reasoning above was right about: the stub CLSID, registering the AUMID for the emitting process, and the only proof that matters — a toast actually reaching Action Center. That remains unverifiable until there is a toast to send.
  - Bridge Windows-hosted WSL through explicit wsl.exe reads and writes of CDX-controlled state rather than sockets, ports, or GUI forwarding.
  - Bound the consumption loop to the adr_005 poll budget, stop it when no session is enabled, back it off after repeated read failures, and size the heartbeat freshness window wider than one poll period.
  - Reuse existing privacy normalization and preference checks; add focused unit and integration-boundary coverage plus documentation.
- Out:
  - Changing provider hook schemas, notification opt-in defaults, quota status collection, or the normal cdx status output.
  - Network listeners, push-notification providers, external services, remote desktops, or cross-machine delivery.
  - Persistent notification archives, searchable history, custom notification templates, or automatic tray startup.
  - Implementing the base tray companion itself; req_035 remains the prerequisite.

# Delivery record
- The spool and heartbeat protocol land in `src/tray_events.py`, and `cdx notify` now publishes to a live tray instead of notifying directly. AC1 holds in both directions: a fresh compatible heartbeat makes the tray the sole owner of the alert, and an absent, stale, schema-mismatched or unreadable one leaves the existing direct path exactly as it was.
- Three properties of the caller decided the design, and each would have been a defect if ignored. `cdx notify` runs inside a provider hook, so it may be killed mid-write: the spool is append-only JSONL and a partial last line is skipped rather than fatal. Several sessions can finish in the same instant: appends are atomic under `O_APPEND`, where a read-modify-write of one JSON array would silently drop all but one — and the losers are notifications nobody ever receives. And a hook cannot wait on a GUI, so publication never blocks and every failure returns False rather than raising inside someone's agent turn.
- Liveness is a heartbeat file, not a pid check: a pid says a process exists, not that it can be reached, and a companion in another WSL namespace would read as reachable when it is not.
- The freshness window is 150 s against a 60 s WSL poll, and a test asserts it exceeds one period. A narrower window reads a healthy tray as stale, and the consequence is precisely the duplicate this slice exists to prevent — once from the tray, once from the fallback.
- Publication sits *below* the composition boundary, so the tray receives the same already-sanitized title and message the direct path would send. It cannot be handed preview text the privacy rules removed; a test asserts a `last_assistant_message` never reaches the spool without opt-in.
- Acknowledgement is idempotent and survives a tray that crashed between showing an event and acknowledging it. The spool is bounded at 32 and keeps the newest: a tray that was down for an hour must not flood the user on return, and an old alert is worth less than a new one.
- The companion reads and acknowledges through `cdx tray events`, `cdx tray ack` and `cdx tray heartbeat` rather than by opening the spool, and that is what satisfies AC4 rather than a note claiming it. On a Windows host serving CDX from WSL the spool lives in the Linux filesystem while the tray runs on Windows: going through `cdx` means the existing `wsl.exe` transport carries events too, with no path translation, no share, no socket, and no assumption that either side can see the other's disk.
- Exercised end to end from the CLI: heartbeat, a hook publishing through `cdx notify`, the event listed, acknowledged, and the list empty again.
- The companion's consumption loop is in place: each poll it heartbeats, collects, draws, then acknowledges. AC3's menu state is a bounded "Recent alerts" section — newest first, eight kept, `!` for attention and `·` for completion — placed below the sessions and above the actions so quota stays what the menu opens onto and the actions never move.
- Order carries the guarantee. Acknowledgement happens *after* the draw, so a companion that dies in between is handed the alert again and shows it twice at worst; acknowledging first would lose it outright. The heartbeat goes first, before collecting, so a companion that has not yet said it is alive is never handed an alert it might then fail to collect.
- Two defects found by running it rather than by reading it. The alerts never appeared under `--print`, because that path called `menu::build` directly and bypassed the loop — a diagnostic surface that lied about what the tray would draw. And the first draw happens *before* the loop, so its alerts stayed unacknowledged for a whole poll period; a companion quit inside that window had shown an alert CDX still considered undelivered.
- `--print` shows alerts but neither heartbeats nor acknowledges, and the asymmetry is deliberate: heartbeating would tell `cdx notify` a tray is listening when the process is about to exit, and acknowledging would consume alerts nothing durable ever displayed.
- `menu::build` was deleted rather than kept as a convenience wrapper. One entry point means no caller can render a menu that silently omits alerts.
- Verified end to end on macOS with the signed bundle: a hook publishes, `--print` shows the alert and leaves it pending, and the running companion writes its heartbeat, draws, and takes the spool to empty.
- The alerts ride along with the snapshot rather than costing their own call, and that came from measuring instead of assuming. Three separate commands per poll cost 220 ms natively where one costs 110 ms, which across WSL — 371-401 ms per crossing — would have tripled the idle cost `adr_005` fixed a budget for. `cdx tray status --json` now carries pending events, and `--beat` writes the heartbeat in the same invocation.
- Measured after the change, on kdesktop through WSL: **374-382 ms**, against 371-401 ms before agent alerts existed. The feature is free at the poll boundary, which is the only place its cost would have been paid forever.
- `--beat` is opt-in rather than implied by reading status: a caller that merely looks must not make `cdx notify` believe a tray is listening. That is what lets `--print` show alerts while leaving them pending.
- AC7's native path is delivered: the companion posts through `UNUserNotificationCenter` from the signed bundle, so an alert carries the CDX name and icon and can be turned off under CDX in System Settings rather than under whatever script delivered it. `block2`, `objc2` and `objc2-foundation` are named as direct dependencies but were already in the tree through `tray-icon`, so the `adr_005` dependency budget is unchanged.
- One guard is load-bearing rather than defensive: `UNUserNotificationCenter` **raises** for a process with no bundle identifier, which is exactly what a development build run as a bare binary is. Without the check the companion would die the first time an agent finished a turn. Verified on both: the bare binary reports `bundle: none (not a bundle)` and `authorization: unavailable`, the signed bundle reports `com.cdx.tray`.
- The authorization state is queried, not assumed. An earlier version reported `granted` whenever the framework was reachable — reachability says nothing about what the user chose, and a diagnostic that guesses is worse than none. `getNotificationSettings` answers on a background queue, so the block hands the value back through a channel with a bounded wait. Observed changing from `not determined` to `denied` on a real run, which is the proof it reflects the system rather than a cache.
- The fallback decision had a real defect, found by reading what the API actually promises. `addNotificationRequest` succeeds whether or not authorization was ever granted: the request is accepted and the banner silently dropped. Trusting its result would mean believing every alert was delivered and never falling back — the one failure that loses notifications outright. Authorization is therefore checked before posting, and anything short of granted goes to `osascript`. Exactly one path runs, so a fallback can never double an alert the tray was built to de-duplicate.
- **Confirmed on screen, 2026-08-11.** After the user granted notifications to CDX in System Settings, `--notifications` reported `granted` — the third distinct value observed on the same machine, after `unavailable` for a bare binary and `denied` before the grant, which is what proves the query reads the system rather than a cache. A companion run then delivered a real alert and the user read it back verbatim: `main` / `autre · needs your attention`.
- The native path is proven rather than inferred. An `osascript` decoy placed first on PATH was never invoked, so the banner came from the bundle and not the fallback — and therefore carried the CDX name and icon. Checking for a running `osascript` afterwards would have proved nothing, since it would have exited by then.
- Still open in this slice: the short-lived icon hint distinct from the menu history, and Windows toast emission through the AppUserModelID, which still has no proof that a toast reaches Action Center. AC6's backoff is satisfied by construction now that alerts ride with the snapshot: one call, one cadence, and the existing `Tick` backs off after three consecutive failures.

# Acceptance criteria
- AC1: A fresh active tray receives one sanitized event and becomes the sole visible notification owner; an absent or stale tray leaves the existing direct path intact.
- AC2: Events are bounded, user-private, idempotently acknowledged, and safe under partial or malformed local state.
- AC3: The tray exposes a clear short-lived hint and recent-event menu state for completion and attention without exposing preview text unless opted in.
- AC4: The Windows host to WSL bridge uses explicit interop commands and has no localhost, port-forwarding, or Linux-GUI prerequisite.
- AC5: Platform capability failure and user notification permission denial avoid duplicate direct notifications while retaining a tray-visible event state.
- AC6: Alert latency is at most one poll period, the loop stops when no session is enabled, backs off after repeated failures, and the heartbeat window exceeds one poll period so a live tray is never read as stale.
- AC7: macOS notifications are emitted from the signed CDX bundle and carry the CDX icon and name; a refused, revoked, or unavailable authorization falls back to osascript delivery without a duplicate, and the authorization state is reportable.
- AC8: Focused tests, existing notification tests, tray-boundary smoke checks, and full project validation pass.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: A fresh active tray receives one sanitized event and becomes the sole visible notification owner; an absent or stale tray leaves the existing direct path intact.
- request-AC2 -> This backlog slice. Proof: AC2: Events are bounded, user-private, idempotently acknowledged, and safe under partial or malformed local state.
- request-AC3 -> This backlog slice. Proof: AC3: The tray exposes a clear short-lived hint and recent-event menu state for completion and attention without exposing preview text unless opted in.
- request-AC4 -> This backlog slice. Proof: AC4: The Windows host to WSL bridge uses explicit interop commands and has no localhost, port-forwarding, or Linux-GUI prerequisite.
- request-AC5 -> This backlog slice. Proof: AC5: Platform capability failure and user notification permission denial avoid duplicate direct notifications while retaining a tray-visible event state.
- request-AC6 -> This backlog slice. Proof: AC4: The Windows host to WSL bridge uses explicit interop commands and has no localhost, port-forwarding, or Linux-GUI prerequisite.
- request-AC7 -> This backlog slice. Proof: AC5: Platform capability failure and user notification permission denial avoid duplicate direct notifications while retaining a tray-visible event state.
- request-AC9 -> This backlog slice. Proof: AC6: Alert latency is at most one poll period, the loop stops when no session is enabled, backs off after repeated failures, and the heartbeat window exceeds one poll period.
- request-AC10 -> This backlog slice. Proof: AC7: macOS notifications are emitted from the signed CDX bundle and carry the CDX icon and name; a refused, revoked, or unavailable authorization falls back to osascript delivery without a duplicate.
- request-AC8 -> This backlog slice. Proof: AC8: Focused tests, existing notification tests, tray-boundary smoke checks, and full project validation pass.

# Decision framing
- Product framing: Not needed
- Architecture framing: Settled in `adr_005_cdx_tray_runtime_and_companion_transport_boundary`

# Links
- Product brief(s): `prod_025_tray_aware_agent_alerts`
- Architecture decision(s): `adr_005_cdx_tray_runtime_and_companion_transport_boundary`
- Request: `req_036_route_cdx_agent_alerts_through_an_active_tray_companion`
- Primary task(s): `task_047_orchestrate_tray_aware_cdx_agent_alert_delivery`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
