## task_047_orchestrate_tray_aware_cdx_agent_alert_delivery - Orchestrate tray-aware CDX agent alert delivery
> From version: 0.17.1
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 93%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-10 20:16:59
> Owner: claude

# AI Context
- Summary: Orchestrate tray-aware CDX agent alert delivery
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.
- Blocked on task_046: this task consumes the companion, the cdx tray status snapshot, and the WSL bridge that task_046 builds. Do not start it while task_046 is open.
- The event spool remains a file, unlike the status snapshot. Its writer is a provider hook and its reader is the tray, two processes that never meet, so it cannot be a command invocation the way status is.
- Alert latency equals the poll period fixed in adr_005, so the delivery design is bounded by that decision rather than free to choose its own cadence.

# Plan
- [x] 1. Confirm the base tray companion is available and trace the existing hook, compose_notification, direct-notification, and session-preference paths end to end.
- [x] 2. Define and test the smallest local heartbeat, event, acknowledgement, expiry, and eviction protocol, preserving hook non-failure and existing privacy boundaries.
- [x] 3. Route cdx notify through that protocol only for a live compatible tray, retaining the current direct OS notification fallback otherwise.
- [x] 4. Implement tray-side hint, recent-event, and native-notification behaviour, including Windows installed-capability and permission handling.
- [x] 5. Add the explicit Windows-to-WSL interop bridge, run focused and platform smoke checks, document the fallback semantics, and validate the workflow corpus.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_082_deliver_agent_hook_events_through_the_active_cdx_tray_with_safe_fallback`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: `cdx notify` publishes to the spool only when the heartbeat is fresh and the schema matches, and skips the direct notification when it does. A test asserts exactly one path runs; verified in the field on macOS, where the user received one banner per alert and never two.
- request-AC2 -> This task. Proof: an absent, stale, schema-mismatched or unreadable heartbeat leaves the direct path untouched, and every failure in publication returns False rather than raising — the caller is a provider hook, so an exception there would break an agent turn. Tested in all four shapes.
- request-AC3 -> This task. Proof: alerts appear as a 45 s counted marker beside the glyph, a bounded eight-entry "Recent alerts" menu section, and one native notification. Acknowledgement happens after the draw, and history is de-duplicated by event id, so a companion that dies mid-draw shows an alert again rather than losing it and never shows one twice.
- request-AC4 -> This task. Proof: publication sits below `compose_notification`, so the tray receives the same already-sanitized title and body the direct path would send. A test asserts a `last_assistant_message` never reaches the spool without the per-session preview opt-in; no raw payload or tool input is persisted.
- request-AC5 -> This task. Proof: the spool is append-only JSONL under the user's own CDX home, versioned, capped at 32 entries keeping the newest, and compacted once acknowledged entries accumulate. A malformed or partial last line is skipped rather than fatal — the writer is a hook that can be killed mid-append. Concurrent hooks cannot lose each other, because `O_APPEND` writes are atomic where a read-modify-write of one JSON array would not be.
- request-AC6 -> This task. Proof: the companion reads and acknowledges through `cdx tray status --beat` and `cdx tray ack`, over the transport it already uses. Verified on kdesktop through both crossings — a hook publishes in WSL, the Windows companion reads back through `wsl.exe`, draws, delivers and empties the spool. No Linux GUI, no listener, no port forwarding, no localhost assumption.
- request-AC7 -> This task. Proof: the Windows companion sends under `com.cdx.tray` once `cdx tray install` has written the Start Menu shortcut, and under PowerShell's identifier until then, resolved per send. `cdx tray doctor` reports the shortcut as `blocked` when it is missing. The event stays visible in the tray either way, and exactly one delivery path runs.
- request-AC8 -> This task. Proof: 771 Python tests and 45 Rust tests cover active-tray routing, fallback, stale heartbeat, duplicate suppression, preview privacy, malformed spool recovery, bounded eviction, poll period and backoff, and the Windows-WSL command construction. Existing notification tests pass unchanged; `npm run lint` and Logics lint are clean.
- request-AC9 -> This task. Proof: measured, not asserted. 374-382 ms per poll across WSL at a 60 s period and 140-145 ms natively at 30 s, so alert latency is at most one period. Polling stops entirely with no enabled session and backs off to 300 s after three consecutive failures. The heartbeat window is 150 s against a 60 s period, and a test asserts it exceeds one period — narrower, and a healthy tray reads as stale and the user gets the alert twice.
- request-AC10 -> This task. Proof: macOS alerts are posted through `UNUserNotificationCenter` from the signed bundle, confirmed on screen by the user who read the alert text back. Authorization is requested once, queried from the system rather than remembered, and reportable via `cdx-tray --notifications` — observed as `unavailable`, `denied` and `granted` on the same machine, which is what proves it is read rather than cached. Anything short of granted falls back to `osascript`, and exactly one path runs. The grant survived a CDX-managed update, verified on the managed macOS host.

# Validation
- (no validation recorded yet)
- 2026-08-11: npm test 771 passed, cargo test 45 passed, cargo clippy zero warnings on aarch64-apple-darwin, x86_64-pc-windows-msvc and x86_64-unknown-linux-gnu, npm run lint clean. Alert delivery confirmed on screen by the operator on macOS and on Windows through WSL; poll cost measured at 374-382ms across WSL and 140-145ms native.
- Finish workflow executed on 2026-08-11.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-11.
- Linked backlog item(s): `item_082_deliver_agent_hook_events_through_the_active_cdx_tray_with_safe_fallback`
- Related request(s): `req_036_route_cdx_agent_alerts_through_an_active_tray_companion`

# Links
- Request: `req_036_route_cdx_agent_alerts_through_an_active_tray_companion`
- Product brief(s): `prod_025_tray_aware_agent_alerts`
- Architecture decision(s): `adr_005_cdx_tray_runtime_and_companion_transport_boundary`
