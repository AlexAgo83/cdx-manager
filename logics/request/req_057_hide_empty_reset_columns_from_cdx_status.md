## req_057_hide_empty_reset_columns_from_cdx_status - Hide empty reset columns from cdx status
> From version: 0.18.6
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 90%
> Complexity: Low
> Theme: Status readability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: Status tables show each reset column only when active displayed session data makes it useful.
- Keywords: status table, reset column, active session, malformed cache value
- Use when: Changing human-readable cdx status table rendering or reset-column visibility.
- Skip when: Changing JSON, detailed status, or quota ranking semantics.

# Needs
- cdx status currently always renders RESETS, RESET 5H, and RESET WEEK, even when every row contains only a dash. Those empty columns make the terminal table wider without helping an operator choose a session.
- An operator should see a reset column only when at least one displayed session has actionable data for that reset type.

# Context
- _format_status_rows builds both normal and small table headers with fixed reset columns, then creates six usage values per row. The same rows still feed recommendation and ranking logic, which must not be changed by presentation-only filtering.
- RESETS is a bonus-reset counter and should be visible only when a displayed row has a positive available count. RESET 5H and RESET WEEK should be independently visible only when their corresponding timestamp exists on a displayed row.
- The human table is the scope. JSON payload fields, detail output, stored status data, and the reset-aware recommendation algorithm remain stable even when a table column is hidden.
- A disabled session renders placeholder usage, so its stored reset fields must not cause a visible column whose every displayed cell is a dash. With no sessions, the empty-table help must also omit reset columns because there is no reset signal.
- Bonus-reset values may be absent, zero, numeric strings, or malformed cached data. Visibility must require a finite positive numeric count; formatting malformed data must not crash status output.

# Acceptance criteria
- AC1: Normal cdx status omits RESETS when no displayed session has a positive reset_credits_available value, omits RESET 5H when no displayed session has reset_5h_at, and omits RESET WEEK when no displayed session has reset_week_at.
- AC2: Each reset column appears independently as soon as at least one displayed row has its actionable value; zero or absent bonus-reset counts do not make RESETS appear.
- AC3: The small status table follows the same visibility rules, and table alignment remains correct for active and disabled rows.
- AC4: JSON status payloads, detailed status reset information, session ranking, and reset-based recommendations retain their current data and behaviour.
- AC5: Focused status-view tests cover all-hidden, each independently visible, mixed rows, zero bonus resets, disabled rows, and small-table output; project and Logics validation pass.
- AC6: Disabled-only reset data and the no-session table do not create reset columns, while a positive active-row count or reset timestamp does.
- AC7: Zero, absent, numeric-string, and malformed bonus-reset values are handled safely and only a positive numeric value makes RESETS visible.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_044_signal_only_cdx_status_reset_columns`
- Architecture decision(s): (none yet)

# References
- src/status_view.py
- src/commands/status.py
- test/test_commands_status_py.py
- README.md

# Backlog
- `item_113_derive_reset_column_visibility_from_rendered_status_data`
- `item_114_prove_conditional_reset_columns_preserve_status_contracts`
