## item_077_clarify_notification_setup_lifecycle_feedback_and_documentation - Clarify notification setup, lifecycle feedback, and documentation
> From version: 0.17.0
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Notifications
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: Clarify notification setup, lifecycle feedback, and documentation
- Keywords: scaffolded-backlog, clarify notification setup, lifecycle feedback, and documentation, implementation-ready
- Use when: Implementing the scaffolded slice for Clarify notification setup, lifecycle feedback, and documentation.
- Skip when: The change belongs to another backlog slice.

# Problem
- The CLI exposes an implementation command next to user commands and leaves the intended setup path implicit.
- A generic settings confirmation hides the practical consequence of changing notifications: hooks are reconciled only at the next interactive launch.
- Users can confuse agent attention alerts with next-ready alerts because both are named as notifications but solve different problems.

# Scope
- In:
  - Add concise task-oriented notification guidance to root help and the main screen using the existing commands.
  - Make direct interactive use of the internal hook target self-explanatory while preserving silent, successful provider-hook execution.
  - Add targeted text feedback for notify preference changes, including the next-launch lifecycle and provider review requirement where applicable.
  - Improve the existing configuration rendering and README wording so all surfaces use the same names and examples.
  - Cover single-session and bulk settings paths plus launch output with focused tests.
- Out:
  - Adding cdx notifications, cdx notify status, or another command hierarchy.
  - Tracking hook trust, installation, or OS delivery state across processes.
  - Changing the hook payload protocol or desktop notification transports.
  - Changing the default notification preference.

# Acceptance criteria
- AC1: Root help and the main screen show an agent-alert setup example and a next-ready example with distinct plain-language descriptions.
- AC2: cdx notify run from a TTY prints a short internal-command explanation and setup example, while a provider hook receives the unchanged zero-error behavior.
- AC3: cdx set and cdx unset for notify emit a concise next-launch confirmation for one or several sessions without changing JSON output semantics.
- AC4: Launch output accurately identifies installed hooks and any required review without treating an unverified hook or unavailable delivery channel as active.
- AC5: cdx config and cdx configs make Notify understandable as an agent-alert preference rather than a generic boolean.
- AC6: README mirrors the CLI vocabulary and marks cdx notify as internal.
- AC7: New focused tests and the full validation suite pass.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: Root help and the main screen show an agent-alert setup example and a next-ready example with distinct plain-language descriptions.
- request-AC2 -> This backlog slice. Proof: AC2: cdx notify run from a TTY prints a short internal-command explanation and setup example, while a provider hook receives the unchanged zero-error behavior.
- request-AC3 -> This backlog slice. Proof: AC3: cdx set and cdx unset for notify emit a concise next-launch confirmation for one or several sessions without changing JSON output semantics.
- request-AC4 -> This backlog slice. Proof: AC4: Launch output accurately identifies installed hooks and any required review without treating an unverified hook or unavailable delivery channel as active.
- request-AC5 -> This backlog slice. Proof: AC5: cdx config and cdx configs make Notify understandable as an agent-alert preference rather than a generic boolean.
- request-AC6 -> This backlog slice. Proof: AC6: README mirrors the CLI vocabulary and marks cdx notify as internal.
- request-AC7 -> This backlog slice. Proof: AC7: New focused tests and the full validation suite pass.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_023_clear_notification_controls`
- Architecture decision(s): (none yet)
- Request: `req_033_make_agent_notification_controls_discoverable_and_self_explanatory`
- Primary task(s): `task_044_orchestrate_discoverable_agent_notification_controls`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
