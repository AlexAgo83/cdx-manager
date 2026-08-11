## item_090_add_an_explicit_capability_safe_action_submenu_to_every_tray_session_row - Add an explicit, capability-safe action submenu to every tray session row
> From version: 0.18.4
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Tray usability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: Add an explicit, capability-safe action submenu to every tray session row
- Keywords: scaffolded-backlog, add an explicit, capability-safe action submenu to every tray session row, implementation-ready
- Use when: Implementing the scaffolded slice for Add an explicit, capability-safe action submenu to every tray session row.
- Skip when: The change belongs to another backlog slice.

# Problem
- A row that launches directly cannot also reveal future controls without hidden gestures or ambiguous clicks.
- Exposing all persistent CDX launch settings as session controls would wrongly imply that they alter an assistant already running.
- Future Logics actions need a bounded and validated extension seam rather than hard-coded tray entries.

# Scope
- In:
  - Extend the shared menu model and every native backend with one per-session submenu whose identity stays bound to the rendered snapshot session.
  - Ship explicit Open session and View launch configuration actions using the existing terminal and WSL command-routing patterns.
  - Represent supported session and plugin actions declaratively, display only available actions, and preserve accessible text plus macOS custom-cell behaviour.
  - Document and test the boundary between current-session actions and next-launch configuration, including failure-safe action omission.
- Out:
  - A graphical configuration editor, mutation controls for launch settings, provider-process control, or automatic restarts.
  - New Logics plugin data, workflow mutations, remote plugins, arbitrary shell execution, or changes to the existing plugin security contract.
  - Changes to capacity ranking, alert unread state, status polling cadence, or tray onboarding.

# Acceptance criteria
- AC1: A session row has one explicit submenu with stable identity and Open session remains available as an intentional action.
- AC2: View launch configuration is truthful about next-launch settings and reaches the correct CDX environment on native and WSL hosts.
- AC3: No action claims to mutate an already-running session unless a future capability explicitly proves that it can do so.
- AC4: Focused Rust and relevant CDX command-routing tests pass with no regression to the capacity-first rows or global tray actions.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: A session row has one explicit submenu with stable identity and Open session remains available as an intentional action.
- request-AC2 -> This backlog slice. Proof: AC2: View launch configuration is truthful about next-launch settings and reaches the correct CDX environment on native and WSL hosts.
- request-AC3 -> This backlog slice. Proof: AC3: No action claims to mutate an already-running session unless a future capability explicitly proves that it can do so.
- request-AC4 -> This backlog slice. Proof: AC4: Focused Rust and relevant CDX command-routing tests pass with no regression to the capacity-first rows or global tray actions.
- request-AC5 -> This backlog slice. Proof: AC4: Focused Rust and relevant CDX command-routing tests pass with no regression to the capacity-first rows or global tray actions.
- request-AC6 -> This backlog slice. Proof: AC4: Focused Rust and relevant CDX command-routing tests pass with no regression to the capacity-first rows or global tray actions.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_032_actionable_cdx_tray_session_controls`
- Architecture decision(s): (none yet)
- Request: `req_043_make_cdx_tray_session_rows_actionable_without_misleading_live_settings`
- Primary task(s): `task_054_orchestrate_actionable_and_truthful_cdx_tray_session_controls`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
