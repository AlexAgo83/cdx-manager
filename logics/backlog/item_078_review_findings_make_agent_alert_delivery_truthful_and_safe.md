## item_078_review_findings_make_agent_alert_delivery_truthful_and_safe - Review findings: make agent alert delivery truthful and safe
> From version: 0.17.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: High
> Theme: Operator workflow and runtime integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: Review findings: make agent alert delivery truthful and safe
- Keywords: backlog-groom, request, review findings: make agent alert delivery truthful and safe, bounded slice
- Use when: Use when implementing or reviewing the delivery slice for Review findings: make agent alert delivery truthful and safe.
- Skip when: Skip when the change is unrelated to this delivery slice or its linked request.

# Problem
`cdx set <name> --notify on` currently tells every selected session that hooks will install on its next interactive launch. `provision()` only supports `claude` and `codex`; `antigravity` and `ollama` silently return without installing anything. The command must report the actual delivery capability for every selected provider, including mixed bulk selections.
A permission-request notification interpolates the provider payload's `tool_name` directly into the body. Unlike the response preview, it has no printable-character normalization or length bound before it is passed to platform notification renderers. Treat it as untrusted display input and constrain it.

# Scope
- In:
  - one coherent delivery slice from the source request
- Out:
  - unrelated sibling slices that should stay in separate backlog items instead of widening this doc

# Acceptance criteria
- AC1: Enabling, disabling, and bulk-updating agent alerts reports whether each targeted provider can have hooks installed; unsupported providers are never described as pending hook installation.
- AC2: A permission-request tool name shown in a desktop notification is printable, single-line, and bounded, while ordinary valid tool names remain identifiable.
- AC3: Coverage exercises an unsupported provider, a mixed provider selection, and malformed or oversized `tool_name` input.
- AC4: Existing Claude and Codex hook installation behaviour and the opt-in response-preview setting remain unchanged.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: Enabling, disabling, and bulk-updating agent alerts reports whether each targeted provider can have hooks installed; unsupported providers are never described as pending hook installation.
- request-AC2 -> This backlog slice. Proof: AC2: A permission-request tool name shown in a desktop notification is printable, single-line, and bounded, while ordinary valid tool names remain identifiable.
- request-AC3 -> This backlog slice. Proof: AC3: Coverage exercises an unsupported provider, a mixed provider selection, and malformed or oversized `tool_name` input.
- request-AC4 -> This backlog slice. Proof: AC4: Existing Claude and Codex hook installation behaviour and the opt-in response-preview setting remain unchanged.

# Decision framing
- Product framing: Not needed
- Product signals: (none detected)
- Product follow-up: No product brief follow-up is expected based on current signals.
- Architecture framing: Not needed
- Architecture signals: (none detected)
- Architecture follow-up: No architecture decision follow-up is expected based on current signals.

# Links
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
- Request: `req_034_review_findings_make_agent_alert_delivery_truthful_and_safe`
- Primary task(s): `task_045_review_findings_make_agent_alert_delivery_truthful_and_safe`

# Priority
- Priority: Medium
- Rationale: Default until groomed.

# Notes
- Hybrid rationale: Derived from request `req_034_review_findings_make_agent_alert_delivery_truthful_and_safe` and kept bounded to one coherent delivery slice.
- Source file: `logics/request/req_034_review_findings_make_agent_alert_delivery_truthful_and_safe.md`.
- Generated locally by logics-manager.
- Task `task_045_review_findings_make_agent_alert_delivery_truthful_and_safe` was finished via `logics-manager flow finish task` on 2026-08-10.

# Tasks
- `task_045_review_findings_make_agent_alert_delivery_truthful_and_safe`
