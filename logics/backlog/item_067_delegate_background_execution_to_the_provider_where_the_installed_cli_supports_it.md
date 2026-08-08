## item_067_delegate_background_execution_to_the_provider_where_the_installed_cli_supports_it - Delegate background execution to the provider where the installed CLI supports it
> From version: 0.14.0
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 20%
> Complexity: Medium
> Theme: Provider surface
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-08

# Problem
- `_spawn_detached_run` reimplements detached execution with PID tracking, `start_new_session`, and a child argv rebuilt by `_detached_child_argv`, while Claude Code now ships `--bg` with `claude agents` and codex-cli ships `cloud` and `exec-server`.
- Deepening the in-house mechanism spends effort on the part of the problem the providers are solving themselves, rather than on cross-account routing, which neither provider can do.
- The in-house path works and is covered by tests, so the answer is delegation where the installed CLI supports it, not removal.

# Preparation findings
- The two providers offer different shapes, and the asymmetry decides how far this slice can go. Claude Code 2.1.226 has `--bg/--background` ("start the session as a background agent and return immediately, manage with `claude agents`") plus a `claude agents` subcommand - a managed lifecycle cdx can query. codex-cli 0.147.0 has `cloud` and `exec-server`, both marked EXPERIMENTAL in `codex --help`.
- Delegating to an experimental Codex surface would trade a working in-house path for one the provider may change without notice. The realistic first target is Claude only, with Codex staying on the in-house path until its surface stabilises - which keeps the slice honest rather than symmetric.
- Capability detection must not be a version comparison. `cdx doctor --check-provider-flags` already establishes the pattern of asking the installed CLI what it accepts; reuse it rather than inventing a second mechanism.
- The hard constraint is the identity boundary: `cdx run --detach` must keep returning cdx's own `run_id`, and `run-status`/`run-tail`/`runs` must keep their shape, while the process is owned by the provider's agent manager rather than by cdx. Mapping the provider's agent handle to the cdx `run_id` is the real work of this slice.
- `_refresh_stale_runs` and `_is_pid_alive` in `src/run_registry.py` reach terminal status by checking a PID cdx owns. A provider-managed agent has no such PID, so reaching a terminal status has to come from querying the provider instead - this is the part most likely to be underestimated.

# Scope
- In:
  - Detect native background capability against the installed provider CLI, by capability rather than by assuming a version.
  - Route `cdx run --detach` to the native mechanism when it is available, keeping one cdx-level `run_id` and the existing JSON payload shape.
  - Keep the in-house detached path as the fallback, unchanged, when no native capability is detected.
  - Record which path a run took, and surface it in the run record.
  - Keep `cdx run-status`, `cdx run-tail` and `cdx runs` behaving identically to the caller regardless of which path was used.
- Out:
  - Removing or rewriting the in-house detached launcher.
  - Codex Cloud task browsing, and Claude cloud or teleport sessions, which are separate capabilities.
  - Any change to the ollama provider.

# Acceptance criteria
- AC1: Capability detection reports whether the installed provider CLI offers native background execution, without assuming a version number.
- AC2: With native capability present, `cdx run --detach` uses it and still returns the cdx `run_id` at launch.
- AC3: With no native capability, the existing in-house path runs unchanged and its tests still pass.
- AC4: The run record names which path was used.
- AC5: `cdx run-status`, `cdx run-tail` and `cdx runs` return the same shape for a run on either path.
- AC6: A run launched through the native path reaches a terminal status in `cdx runs` without a supervising cdx process.

# AC Traceability
- request-AC11 -> This backlog slice. Proof: AC1: Capability detection reports whether the installed provider CLI offers native background execution, without assuming a version number.
- request-AC12 -> This backlog slice. Proof: AC2: With native capability present, `cdx run --detach` uses it and still returns the cdx `run_id` at launch.
- request-AC13 -> This backlog slice. Proof: AC3: With no native capability, the existing in-house path runs unchanged and its tests still pass.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_018_executable_quota_routing`
- Architecture decision(s): (none yet)
- Request: `req_028_turn_quota_awareness_from_advice_into_execution_across_accounts_and_providers`
- Primary task(s): `task_039_orchestrate_executable_quota_routing_across_accounts_and_providers`

# AI Context
- Summary: Delegate background execution to the provider where the installed CLI supports it
- Keywords: scaffolded-backlog, delegate background execution to the provider where the installed cli supports it, implementation-ready
- Use when: Implementing the scaffolded slice for Delegate background execution to the provider where the installed CLI supports it.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
