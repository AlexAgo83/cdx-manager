## item_121_make_detached_run_registry_persistence_durable_and_bounded - Make detached-run registry persistence durable and bounded
> From version: 0.19.1
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Runtime resilience
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-13 22:09:01

# AI Context
- Summary: Align detached-run registry durability and lock timeout behaviour across supported platforms.
- Keywords: detached, run, registry, persistence, durable, bounded
- Use when: Changing runs.json persistence or concurrent detached-run operations.
- Skip when: Replacing JSON registry storage.

# Problem
- runs.json is the recovery source for detached work but does not fsync its file or parent directory after replacement.
- POSIX registry locking can block forever while Windows uses a bounded timeout.

# Scope
- In:
  - Reuse the existing atomic-write durability pattern for the run registry.
  - Use a bounded POSIX non-blocking lock acquisition compatible with the existing Windows timeout semantics.
  - Add crash-safety and lock-timeout regression tests.
- Out:
  - Replacing JSON storage with a database.
  - Changing run IDs or public run-report payloads.

# Acceptance criteria
- Registry writes fsync both file content and its parent directory before reporting success where supported.
- A stuck lock holder produces a bounded, actionable error on POSIX and Windows.
- Existing concurrent run-registry behaviour remains covered by tests.

# AC Traceability
- request-AC4 -> This backlog slice. Proof: Registry writes fsync both file content and its parent directory before reporting success where supported.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_047_reliable_delivery_and_runtime_contracts`
- Architecture decision(s): (none yet)
- Request: `req_061_harden_repository_reliability_release_verification_and_cli_contracts`
- Primary task(s): `task_071_orchestrate_repository_reliability_and_release_contract_hardening`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
