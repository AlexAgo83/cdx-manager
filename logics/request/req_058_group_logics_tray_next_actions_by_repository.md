## req_058_group_logics_tray_next_actions_by_repository - Group Logics tray next actions by repository
> From version: 0.18.6
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Tray navigation
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: group, logics, tray, next, actions, repository
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Needs
- The Logics tray card currently picks one repository and renders its at-most-two rows flat, prefixed with the repository name. When several repositories have work, an operator cannot scan each repository independently or discover its next action from a repository submenu.
- The tray should group Logics work by repository. Opening a repository submenu should show that repository's blocked and next actionable documents, with each action opening the focused viewer in the correct repository.

# Context
- tray_logics queries bounded logics-manager status payloads per repository root, but _card_from_status currently selects a single card. The plugin-card snapshot contract has only flat rows and the Rust companion only renders flat card actions.
- A repository group needs a stable display label plus rows that retain the already-proven root and logics.focus action identity. The companion must never infer a root from a label or an array position.
- Nested submenus are available in the native tray menu. The new optional grouped-card field must preserve legacy flat rows when CDX and the companion versions differ, and remain bounded so a plugin cannot turn the quota tray into a document browser.

# Acceptance criteria
- AC1: When Logics reports work in multiple repository roots, the tray renders a deterministic repository submenu for each bounded group instead of selecting one global repository row.
- AC2: Each repository submenu shows that repository's blocked document when present and its next active task when present; labels identify the action without repeating the repository name inside its own submenu.
- AC3: Every focused row carries the repository root and stable logics.focus reference through the Python snapshot validation and Rust action callback, so clicking it opens the correct focused viewer.
- AC4: Repository-group ordering, per-group row limits, and total group limits are deterministic and bounded; an empty repository contributes no submenu, while Open Logics and Refresh Logics remain card-wide actions.
- AC5: Older flat plugin cards continue to render as before, malformed groups are safely ignored, and snapshot schema compatibility remains forward-safe.
- AC6: Python and Rust tests cover multiple roots, group ordering and bounds, blocked-plus-next rows, action-root propagation, legacy flat cards, and native submenu rendering; project and Logics validation pass.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_045_repository_oriented_logics_tray_navigation`
- Architecture decision(s): (none yet)

# References
- src/tray_logics.py
- src/tray_plugins.py
- src/commands/tray.py
- tray/src/snapshot.rs
- tray/src/menu.rs
- test/test_tray_plugins_py.py
- tray/src/menu.rs

# Backlog
- `item_115_publish_bounded_logics_repository_groups_in_the_tray_card`
- `item_116_render_logics_repository_groups_as_native_tray_submenus`
