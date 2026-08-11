## req_036_route_cdx_agent_alerts_through_an_active_tray_companion - Route CDX agent alerts through an active tray companion
> From version: 0.17.1
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Complexity: High
> Theme: Desktop integration
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: Route CDX agent alerts through an active tray companion
- Keywords: request-chain-scaffold, route cdx agent alerts through an active tray companion, development-ready
- Use when: You need to implement or review the scaffolded workflow for Route CDX agent alerts through an active tray companion.
- Skip when: The change is unrelated to this scaffolded request chain.

# Needs
- Agent completion and attention hooks already compose a safe session and repository notification, but they bypass the planned tray companion when it is active.
- An active tray should become the single visible delivery owner: it can show a transient icon hint, retain the recent event in its menu, and issue the native notification without duplicate operating-system toasts.
- A missing, stopped, old, or unreachable tray must preserve the current direct desktop notification behaviour and must never delay, fail, or alter an agent turn.
- The Windows tray must receive events from CDX running in WSL without assuming bidirectional localhost networking, which varies between NAT and mirrored WSL modes.

# Context
- src/agent_notify.py already normalizes provider hook payloads, derives the safe title/body through compose_notification, honours the existing notify and notify-preview opt-ins, and deliberately swallows all hook failures.
- src/notify.py currently delivers direct OS notifications through osascript, notify-send, or PowerShell and already identifies WSL as a Windows-hosted delivery boundary.
- The tray companion request req_035 is a prerequisite. Its installed native companion owns the system icon and can emit native notifications; the implementation must not add a second persistent tray process.
- A local, bounded event spool with a short tray heartbeat avoids blocking hook execution and avoids assuming that WSL can connect to a Windows-hosted localhost endpoint. On Windows plus WSL, the host tray can read and update that state through explicit wsl.exe calls.
- A spool consumed by polling means alert latency equals the poll period, so the period is a product decision, not an implementation detail. adr_005 sets it at 30 seconds natively and 60 seconds across the WSL boundary, which is the worst-case delay between an agent finishing and its alert appearing.
- Each wsl.exe poll keeps the WSL VM alive and defeats vmIdleTimeout, so polling must stop when no session is enabled and back off after repeated failures rather than run unconditionally.
- Since Big Sur a macOS notification carries the icon and name of the bundle that sent it, and no API can override that. Today's osascript path is therefore attributed to Script Editor. Sending from the signed CDX bundle is the only way to show the CDX identity, which ties this request to the adr_005 signing decision.
- The tray notification capability must be exercised only from an installed companion on Windows. Windows toasts require a registered AppUserModelID, which is a platform constraint rather than a property of the chosen tray runtime, so cdx tray install must create that registration.

# Acceptance criteria
- AC1: When a compatible tray companion has a fresh local heartbeat, cdx notify publishes one sanitized agent event for the tray and does not also send the existing direct desktop notification.
- AC2: When no fresh heartbeat exists, publishing fails, the tray is incompatible, or the tray is stopped, cdx notify preserves the current direct desktop notification fallback and still exits successfully.
- AC3: The tray renders completion and attention events as a short temporary icon hint, a bounded recent-event menu entry, and one native local notification; repeated consumption or restart does not create duplicate notifications for the same event id.
- AC4: The tray route receives only the already-normalized title/body from compose_notification. Assistant-response preview content remains absent unless the existing per-session notify-preview preference is enabled, and arbitrary provider payload or tool input is never persisted or rendered.
- AC5: The event spool is local, bounded, versioned, private to the current user, and safely recovers from malformed, partial, stale, or unacknowledged entries without growing unbounded or blocking a provider hook.
- AC6: macOS and supported Linux tray processes use the local state directly. A Windows-hosted tray serving CDX in WSL exchanges heartbeat and event data through explicit WSL interop, without requiring a Linux GUI, a LAN listener, port-forwarding, or a localhost-networking assumption.
- AC7: Windows tray notification delivery is enabled only after the tray companion is installed and reports native-notification capability; unavailable permission or capability leaves the event visible in the tray and never falls back into duplicate direct delivery.
- AC10: macOS tray notifications are emitted from the signed CDX bundle so they carry the CDX icon and name, authorization is requested once and its state is reportable, and a refused or unavailable grant falls back to the existing osascript delivery without producing a duplicate. The grant survives a companion update, or the fallback is used and the limitation is documented.
- AC8: Focused tests cover active-tray routing, fallback routing, stale heartbeat, duplicate-event suppression, preview privacy, malformed spool recovery, bounded eviction, poll period and back-off, and Windows-WSL command construction; existing notification tests and project validation pass.
- AC9: Tray-routed alert latency is bounded and documented: at most one poll period, 30 seconds natively and 60 seconds across the Windows-to-WSL boundary. Polling stops when no session is enabled and backs off after repeated read failures, so an idle machine is not kept awake and a stopped WSL distribution is not restarted by the tray. The heartbeat freshness window is wider than one poll period so a healthy tray is never mistaken for a stale one.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_025_tray_aware_agent_alerts`
- Architecture decision(s): `adr_005_cdx_tray_runtime_and_companion_transport_boundary`

# References
- src/agent_notify.py
- src/notify.py
- src/commands/launch.py
- src/commands/settings.py
- src/cli_args.py
- test/test_agent_notify_py.py
- test/test_notify_py.py
- logics/request/req_035_add_an_optional_cross_platform_cdx_tray_usage_monitor.md
- logics/product/prod_024_cdx_tray_usage_monitor.md
- https://v2.tauri.app/plugin/notification/
- https://learn.microsoft.com/en-us/windows/wsl/networking
- https://learn.microsoft.com/en-us/windows/dev-environment/wsl-interop

# Backlog
- `item_082_deliver_agent_hook_events_through_the_active_cdx_tray_with_safe_fallback`
