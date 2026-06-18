## task_018_keep_codex_fast_mode_opt_in_and_normalize_launch_settings - Keep Codex Fast mode opt-in and normalize launch settings
> From version: 0.9.2
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# Definition of Done (DoD)
- [ ] The backlog scope is implemented.
- [ ] Acceptance criteria are covered.
- [ ] Validation passes.

# Backlog
- `item_018_keep_codex_fast_mode_opt_in_and_normalize_launch_settings`


```mermaid
%% logics-kind: task
%% logics-signature: task|keep-codex-fast-mode-opt-in-and-normaliz|item-018-keep-codex-fast-mode-opt-in-and|1-confirm-scope|run-python3-m-logics-manager-lint-requi
flowchart TD
    Backlog[Backlog item] --> Build[Implementation]
    Build --> Validate[Validation]
    Validate --> Close[Finish workflow]
```

# Acceptance criteria
- AC1: New Codex sessions created by `cdx` do not launch with Codex `service_tier = "fast"` unless the user explicitly configured Fast on.
- AC2: `cdx set <session> --fast off`, default launch state, and any safe-reset/unset flow actively prevent Codex Fast service tier usage, including when a session `CODEX_HOME/config.toml` already contains `service_tier = "fast"`.
- AC3: `cdx set <session> --fast on` uses current Codex semantics for Codex sessions instead of only lowering `model_reasoning_effort`, or the setting is renamed/split so Codex Fast tier and low reasoning effort are not conflated.
- AC4: Provider-neutral "low effort" behavior remains available through `--power low` and does not implicitly opt users into Codex Fast tier.
- AC5: Interactive and headless Codex launches use explicit, documented Codex CLI/config overrides for Fast-on and Fast-off behavior.
- AC6: Persisted `power` values for Codex align with documented Codex `model_reasoning_effort` values: support `minimal|low|medium|high|xhigh` where compatible, and remove, reject, or migrate undocumented `max` for Codex.
- AC7: `cdx run --power` and `cdx run --reasoning-effort` use the same Codex-compatible reasoning effort contract as persisted launch settings, or clearly document and enforce why headless has a narrower contract.
- AC8: Session selection and priority ranking handle `minimal`, `low`, `medium`, `high`, and `xhigh` deterministically without treating unknown values as silently equivalent to `low`.
- AC9: `cdx unset --all` and related unset/default flows preserve the product safety rule that Codex Fast remains off by default, rather than falling through to an unsafe provider or stale session config default.
- AC10: README/help/config output explain that Codex Fast mode is opt-in, more expensive in credits, and disabled by default under `cdx`; they also distinguish Codex Fast tier from reasoning effort.
- AC11: Regression tests cover Codex launch args for default Fast-off, explicit Fast-off, explicit Fast-on, coexistence with `--power minimal|low|medium|high|xhigh`, rejection or migration of `max`, and interactive/headless parity.
- AC12: Any migration handles existing session launch records where `fast=true` currently meant low effort, without silently turning on paid Codex Fast tier.

# Validation
- Run `python3 -m logics_manager lint --require-status`.
- Run `python3 -m logics_manager flow finish task task_018_keep_codex_fast_mode_opt_in_and_normalize_launch_settings.md` after implementation.

# Report
- Implementation complete.

# AI Context
- Summary: Implement keep codex fast mode opt-in and normalize launch settings.
- Keywords: task, implementation, backlog, runtime, python
- Use when: You need a bounded implementation task for a backlog item.
- Skip when: The work is still at the request or backlog shaping stage.

# Links
- Request: `req_006_codex_fast_mode_opt_in_upgrade_safe`
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# AC Traceability
- request-AC1 -> This task. Proof: Planned implementation evidence: New Codex sessions created by `cdx` do not launch with Codex `service_tier = "fast"` unless the user explicitly configured Fast on.
- request-AC2 -> This task. Proof: Planned implementation evidence: `cdx set <session> --fast off`, default launch state, and any safe-reset/unset flow actively prevent Codex Fast service tier usage, including when a session `CODEX_HOME/config.toml` already contains `service_tier = "fast"`.
- request-AC3 -> This task. Proof: Planned implementation evidence: `cdx set <session> --fast on` uses current Codex semantics for Codex sessions instead of only lowering `model_reasoning_effort`, or the setting is renamed/split so Codex Fast tier and low reasoning effort are not conflated.
- request-AC4 -> This task. Proof: Planned implementation evidence: Provider-neutral "low effort" behavior remains available through `--power low` and does not implicitly opt users into Codex Fast tier.
- request-AC5 -> This task. Proof: Planned implementation evidence: Interactive and headless Codex launches use explicit, documented Codex CLI/config overrides for Fast-on and Fast-off behavior.
- request-AC6 -> This task. Proof: Planned implementation evidence: Persisted `power` values for Codex align with documented Codex `model_reasoning_effort` values: support `minimal|low|medium|high|xhigh` where compatible, and remove, reject, or migrate undocumented `max` for Codex.
- request-AC7 -> This task. Proof: Planned implementation evidence: `cdx run --power` and `cdx run --reasoning-effort` use the same Codex-compatible reasoning effort contract as persisted launch settings, or clearly document and enforce why headless has a narrower contract.
- request-AC8 -> This task. Proof: Planned implementation evidence: Session selection and priority ranking handle `minimal`, `low`, `medium`, `high`, and `xhigh` deterministically without treating unknown values as silently equivalent to `low`.
- request-AC9 -> This task. Proof: Planned implementation evidence: `cdx unset --all` and related unset/default flows preserve the product safety rule that Codex Fast remains off by default, rather than falling through to an unsafe provider or stale session config default.
- request-AC10 -> This task. Proof: Planned implementation evidence: README/help/config output explain that Codex Fast mode is opt-in, more expensive in credits, and disabled by default under `cdx`; they also distinguish Codex Fast tier from reasoning effort.
- request-AC11 -> This task. Proof: Planned implementation evidence: Regression tests cover Codex launch args for default Fast-off, explicit Fast-off, explicit Fast-on, coexistence with `--power minimal|low|medium|high|xhigh`, rejection or migration of `max`, and interactive/headless parity.
- request-AC12 -> This task. Proof: Planned implementation evidence: Any migration handles existing session launch records where `fast=true` currently meant low effort, without silently turning on paid Codex Fast tier.
