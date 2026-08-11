## req_040_keep_the_cdx_tray_menu_globally_ordered_by_remaining_capacity - Keep the CDX tray menu globally ordered by remaining capacity
> From version: 0.18.4
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Low
> Theme: Tray usability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: Keep the CDX tray menu globally ordered by remaining capacity
- Keywords: request-chain-scaffold, keep the cdx tray menu globally ordered by remaining capacity, development-ready
- Use when: You need to implement or review the scaffolded workflow for Keep the CDX tray menu globally ordered by remaining capacity.
- Skip when: The change is unrelated to this scaffolded request chain.

# Needs
- The tray already receives sessions globally sorted by urgency and remaining capacity, which directly answers which session needs attention first.
- Grouping those rows by provider reorders the menu, hides the global capacity ranking, and creates an index mismatch in the macOS custom row renderer when sessions from providers interleave.
- Users still need to identify a session's provider, but that information belongs on the row rather than in a grouping that changes the reading order.

# Context
- src/tray_contract.py builds snapshot sessions in global urgency order: severity, remaining capacity, then session name.
- tray/src/menu.rs groups that ordered list by provider and assigns new sequential ActionId::Session indices. tray/src/runner.rs resolves those indices against the original ungrouped snapshot list; macOS custom cells consequently draw a session under the wrong provider heading after a capacity change reorders interleaved providers.
- The plain menu label and macOS custom cell currently omit the provider because the heading was assumed to supply it. Removing headings therefore requires provider text on every row, including the accessible text fallback.
- The existing session action opens a named CDX session. Its identifier must stay bound to the same session displayed in the row on macOS, Windows, and Linux.

# Acceptance criteria
- AC1: The tray menu displays every enabled session in the same global urgency and remaining-capacity order supplied by the snapshot, with no provider group headings or provider-driven reordering.
- AC2: Every session row states its provider in the native text fallback and the macOS custom row, so provider identity remains available without relying on a group heading or colour.
- AC3: A rendered row, its action identifier, and its session-launch target always refer to the same session when Codex, Claude, and other providers are interleaved and one session's percentage changes.
- AC4: The existing gauges, capacity figures, freshness, reset text, alert history, refresh action, and no-enabled-session state remain unchanged.
- AC5: Focused Rust tests cover an interleaved multi-provider snapshot, a capacity reorder, row/provider rendering, and click-target identity; the tray validation suite passes.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_029_capacity_first_cdx_tray_menu`
- Architecture decision(s): (none yet)

# References
- src/tray_contract.py
- tray/src/menu.rs
- tray/src/runner.rs
- tray/src/mac_cell.rs
- tray/src/backend.rs
- test/test_tray_contract_py.py
- tray/Cargo.toml

# Backlog
- `item_087_flatten_the_tray_session_menu_while_preserving_provider_context`
