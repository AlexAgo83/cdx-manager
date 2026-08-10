## req_037_add_a_first_party_logics_plugin_surface_to_the_cdx_tray - Add a first-party Logics plugin surface to the CDX tray
> From version: 0.17.1
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: High
> Theme: Desktop integration
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-10 13:29:55

# AI Context
- Summary: Add a first-party Logics plugin surface to the CDX tray
- Keywords: request-chain-scaffold, add a first-party logics plugin surface to the cdx tray, development-ready
- Use when: You need to implement or review the scaffolded workflow for Add a first-party Logics plugin surface to the CDX tray.
- Skip when: The change is unrelated to this scaffolded request chain.

# Needs
- The optional tray needs a safe extension point so product-specific information can appear without turning the tray companion into a copy of every command-line tool.
- Logics is the first extension: its machine-readable status already exposes active tasks, blocked documents, draft requests, counts, and next actions that are useful at a glance.
- The Logics integration should ship in cdx-manager and work only when logics-manager is available, with no separate package, remote marketplace, downloaded plugin code, or mandatory dependency.
- Future extensions need one small compatible data contract, but v1 must not over-design a general plugin ecosystem before a second real plugin exists.

# Context
- logics-manager status --format json exposes active_tasks, blocked_docs, draft_requests, counts, and next_actions. It is the only Logics data source needed for the first tray card.
- cdx view already provides the user-facing browser entry point and focus workflow. The Logics tray card should open it through the CDX-owned command path rather than embed a second document viewer.
- The base tray companion request req_035 owns the native icon, menu, status snapshot, installed companion lifecycle, and WSL bridge. The tray-aware alert request req_036 owns event delivery; this request must not duplicate either subsystem.
- The CDX core, not the native tray executable, should own plugin discovery, availability checks, timeouts, JSON validation, and invocation in the correct native or WSL environment. The tray receives one bounded snapshot from cdx.
- The card rides the snapshot and poll cadence settled in adr_005 and adds no loop of its own, so on the Windows-to-WSL path the card is refreshed by the same wsl.exe tick as the rest of the snapshot rather than by a second interop call.
  - The v1 card is fixed: one summary line in the form Logics · blocked count · ready count, followed by at most two rows ordered as the first blocked document then the highest-priority ready task. Each row opens its focused CDX view; the general Open Logics action opens the global view. The shared tray refreshes the card every 60 seconds and on manual refresh.

# Acceptance criteria
- AC1: cdx exposes a versioned, bounded tray-plugin snapshot contract that represents plugin identity, availability, severity, short summary, a small list of display rows, and declared action ids; invalid or slow plugin output cannot break the base CDX tray status.
- AC2: The built-in Logics adapter is delivered in cdx-manager, is disabled unless explicitly enabled, and reports a clear unavailable state without an error when logics-manager is not installed or returns invalid status data.
- AC3: When enabled and available, the Logics tray card derives its information only from logics-manager status --format json and renders one summary line with blocked and ready counts plus at most two rows: the first blocked document, then the highest-priority ready task, without parsing Logics markdown directly.
- AC4: Each Logics row opens cdx view focused on its documented reference, while the declared Open Logics action opens the global view; the card also exposes refresh, but no viewer, arbitrary plugin-provided shell string, or Logics workflow mutation.
- AC5: The native tray companion receives the Logics card only through the shared CDX snapshot and refreshes it at most every 60 seconds or on manual refresh, without adding a second tray icon, long-running plugin process, or independent polling loop.
- AC6: The same Logics adapter works for native CDX and Windows-hosted WSL through the base tray bridge, with CDX selecting the correct logics-manager environment rather than the Windows tray executable assuming a path.
- AC7: cdx tray plugin enable logics, disable logics, and status are explicit, reversible, documented operations; normal cdx and tray use do not implicitly enable the integration, but an available disabled Logics manager is identified once as activatable.
- AC8: Focused tests cover snapshot schema validation, timeout and malformed-output isolation, disabled/unavailable states, Logics JSON mapping, declared action routing, WSL command selection, and no-mutation behaviour; existing project validation passes.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_026_extensible_cdx_tray_with_a_first_party_logics_card`
- Architecture decision(s): `adr_005_cdx_tray_runtime_and_companion_transport_boundary`

# References
- src/cli.py
- src/cli_args.py
- src/cli_view.py
- src/logics_view.py
- src/commands/status.py
- README.md
- logics/request/req_035_add_an_optional_cross_platform_cdx_tray_usage_monitor.md
- logics/request/req_036_route_cdx_agent_alerts_through_an_active_tray_companion.md
- logics/product/prod_024_cdx_tray_usage_monitor.md
- logics/product/prod_025_tray_aware_agent_alerts.md

# Backlog
- `item_083_add_the_cdx_tray_plugin_contract_and_built_in_logics_status_card`
