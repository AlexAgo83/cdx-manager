## item_083_add_the_cdx_tray_plugin_contract_and_built_in_logics_status_card - Add the CDX tray plugin contract and built-in Logics status card
> From version: 0.17.1
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: High
> Theme: Desktop integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-10 13:29:56

# AI Context
- Summary: Add the CDX tray plugin contract and built-in Logics status card
- Keywords: scaffolded-backlog, add the cdx tray plugin contract and built-in logics status card, implementation-ready
- Use when: Implementing the scaffolded slice for Add the CDX tray plugin contract and built-in Logics status card.
- Skip when: The change belongs to another backlog slice.

# Problem
- Without a narrow adapter boundary, each future tray integration would leak tool-specific invocation and rendering logic into the native companion.
- A generic plugin platform now would add discovery, trust, packaging, and lifecycle complexity before there is evidence that it is needed.

# Scope
- In:
  - Define a small versioned JSON card schema and one CDX-owned adapter registry with bounded invocation and validation.
  - Implement and ship a Logics adapter in this repository that maps only logics-manager status JSON into one blocked/ready summary and at most the first blocked document plus highest-priority ready task.
  - Add explicit enable, disable, and status commands plus safe action ids that route refresh, the global Open Logics view, and focused row views through CDX; identify an available disabled Logics manager once without enabling it.
  - Pass the resulting card only through the base tray snapshot, refresh it at most every 60 seconds or on manual refresh, preserve WSL environment selection in CDX, and document the optional integration.
  - Add focused contract, failure-isolation, mapping, action, and WSL-boundary tests.
- Out:
  - A marketplace, automatic plugin discovery, installation from URLs, plugin auto-update, or plugin execution inside the native tray process.
  - Arbitrary plugin-defined shell commands, direct plugins-to-tray IPC, unrestricted menu layouts, or custom embedded web views.
  - Changing Logics documents or lifecycle state from the tray, including start, finish, closeout, or promotion actions.
  - Implementing the base tray or tray-aware hook-notification features, which remain prerequisite requests.

# Acceptance criteria
- AC1: CDX produces a tested versioned snapshot containing zero or more bounded plugin cards and ignores malformed, unknown, slow, or unavailable adapters without harming core tray data.
- AC2: The bundled Logics adapter is opt-in, uses only status JSON, renders one blocked/ready summary plus at most two actionable rows, and stays silent when Logics is unavailable.
- AC3: The tray refreshes the card at most every 60 seconds or on demand and routes only refresh, global Open Logics, and focused-row action ids through CDX.
- AC4: Native and WSL installations resolve the Logics command through CDX rather than tray-specific executable paths.
- AC5: cdx tray plugin enable logics, disable logics, and status are explicit, reversible, and documented; nothing enables the integration implicitly, and an available disabled Logics manager is identified once as activatable.
- AC6: Plugin activation, status, privacy, failure semantics, and the intentionally absent marketplace are documented; focused tests and project validation pass.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: CDX produces a tested versioned snapshot containing zero or more bounded plugin cards and ignores malformed, unknown, slow, or unavailable adapters without harming core tray data.
- request-AC2 -> This backlog slice. Proof: AC2: The bundled Logics adapter is opt-in, uses only status JSON, and stays silent when Logics is unavailable.
- request-AC3 -> This backlog slice. Proof: AC2: The adapter renders one blocked/ready summary plus at most two actionable rows from status JSON only.
- request-AC4 -> This backlog slice. Proof: AC3: The card routes only refresh, global Open Logics, and focused-row action ids through CDX.
- request-AC5 -> This backlog slice. Proof: AC3: The tray refreshes the card at most every 60 seconds or on demand, through the shared snapshot and with no independent polling loop.
- request-AC6 -> This backlog slice. Proof: AC4: Native and WSL installations resolve the Logics command through CDX rather than tray-specific executable paths.
- request-AC7 -> This backlog slice. Proof: AC5: cdx tray plugin enable logics, disable logics, and status are explicit, reversible, and documented, and nothing enables the integration implicitly.
- request-AC8 -> This backlog slice. Proof: AC6: Plugin activation, status, privacy, failure semantics, and the intentionally absent marketplace are documented; focused tests and project validation pass.

# Decision framing
- Product framing: Not needed
- Architecture framing: Settled in `adr_005_cdx_tray_runtime_and_companion_transport_boundary`

# Links
- Product brief(s): `prod_026_extensible_cdx_tray_with_a_first_party_logics_card`
- Architecture decision(s): `adr_005_cdx_tray_runtime_and_companion_transport_boundary`
- Request: `req_037_add_a_first_party_logics_plugin_surface_to_the_cdx_tray`
- Primary task(s): `task_048_orchestrate_the_first_party_logics_cdx_tray_plugin`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
