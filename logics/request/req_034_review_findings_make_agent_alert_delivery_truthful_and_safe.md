## req_034_review_findings_make_agent_alert_delivery_truthful_and_safe - Review findings: make agent alert delivery truthful and safe
> From version: 0.17.0
> Schema version: 1.0
> Status: Ready
> Understanding: 100%
> Confidence: 95%
> Complexity: Medium
> Theme: Notification reliability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: Make agent-alert status messages match actual provider support, and constrain provider-supplied tool names before they reach desktop notification renderers.
- Keywords: notification hooks, provider capability, permission request, desktop notification, input normalization
- Use when: A session enables agent alerts or a provider hook reports a permission request.
- Skip when: The notification is a local quota/ready alert rather than a provider hook.

# Needs
- `cdx set <name> --notify on` currently tells every selected session that hooks will install on its next interactive launch. `provision()` only supports `claude` and `codex`; `antigravity` and `ollama` silently return without installing anything. The command must report the actual delivery capability for every selected provider, including mixed bulk selections.
- A permission-request notification interpolates the provider payload's `tool_name` directly into the body. Unlike the response preview, it has no printable-character normalization or length bound before it is passed to platform notification renderers. Treat it as untrusted display input and constrain it.

# Context
- Review evidence: `src/config.py:4-8` declares four supported providers; `src/agent_notify.py:157-161` provisions only Claude and Codex. `src/commands/settings.py:44-49` always promises hook installation after enabling alerts, while `src/commands/launch.py:113-120` ignores the unsupported-provider `False` result.
- Review evidence: `src/agent_notify.py:77-78` appends `tool_name` verbatim, while `src/agent_notify.py:84-93` already normalizes and bounds response-preview text. `src/notify.py:94-111` sends the composed text to platform-specific renderers.
- Verification completed during review: `git diff --check HEAD~4..HEAD`, `npm run lint`, and the full Python test suite (684 passed).

# Acceptance criteria
- AC1: Enabling, disabling, and bulk-updating agent alerts reports whether each targeted provider can have hooks installed; unsupported providers are never described as pending hook installation.
- AC2: A permission-request tool name shown in a desktop notification is printable, single-line, and bounded, while ordinary valid tool names remain identifiable.
- AC3: Coverage exercises an unsupported provider, a mixed provider selection, and malformed or oversized `tool_name` input.
- AC4: Existing Claude and Codex hook installation behaviour and the opt-in response-preview setting remain unchanged.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# References
- `logics_manager/flow.py`
- `logics_manager/assist.py`
- `tests/python/test_logics_manager_cli.py`

# Backlog
- none
