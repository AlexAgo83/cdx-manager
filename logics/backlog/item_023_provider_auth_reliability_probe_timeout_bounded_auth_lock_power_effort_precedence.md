## item_023_provider_auth_reliability_probe_timeout_bounded_auth_lock_power_effort_precedence - Provider auth reliability: probe timeout, bounded auth lock, power/effort precedence
> From version: 0.10.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Low
> Theme: Operator workflow
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- Auth status probes run without a subprocess timeout on every launch/run/doctor; a hung provider CLI blocks the command forever.
- The codex auth lock yields False under contention but the protected body runs anyway, permitting the concurrent auth.json refresh the lock exists to prevent.
- A stored reasoning_effort launch key silently overrides --power forever: set does not clear it and unset does not accept it.

# Scope
- In:
  - Add timeout=15 to the auth probe subprocess calls; map TimeoutExpired to an unknown/degraded probe result.
  - Replace the run-anyway contention path with a bounded blocking acquire (retry up to ~10s), then explicit failure or degradation.
  - set_launch_settings with power removes reasoning_effort from the merged dict; unset_launch_settings allows reasoning_effort.
- Out:
  - Per-session provider login; cross-home token-rotation redesign (document the limitation only).

# Acceptance criteria
- A probe subprocess that never returns causes a degraded status within 15s, not a hang.
- Under lock contention the second writer waits or fails explicitly; it never refreshes auth.json unlocked.
- After set --power on a session with stored reasoning_effort, the launch uses the new power; unset reasoning_effort succeeds.

# Report
- Provider auth probes now pass a 15s subprocess timeout and degrade to unauthenticated on timeout instead of hanging.
- Interactive Codex launches acquire the auth lock with a bounded 10s wait and fail explicitly if it cannot be acquired.
- Setting `power` clears stored `reasoning_effort` fields, and `cdx unset --reasoning-effort` is supported.
- Validation: `python3 -m unittest discover -s test -p 'test_runtime_py.py'`; `python3 -m unittest discover -s test -p 'test_session_service_py.py'`; `python3 -m unittest discover -s test -p 'test_cli_py.py' -k reasoning`.

# AC Traceability
- request-AC2 -> This backlog slice. Proof: A probe subprocess that never returns causes a degraded status within 15s, not a hang.
- request-AC3 -> This backlog slice. Proof: Under lock contention the second writer waits or fails explicitly; it never refreshes auth.json unlocked.
- request-AC4 -> This backlog slice. Proof: After set --power on a session with stored reasoning_effort, the launch uses the new power; unset reasoning_effort succeeds.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_003_code_review_remediation_wave_2026_07`
- Architecture decision(s): (none yet)
- Request: `req_010_address_july_2026_code_review_findings_data_safety_reliability_and_cleanup`
- Primary task(s): `task_021_orchestrate_july_2026_code_review_remediation`

# AI Context
- Summary: Provider auth reliability: probe timeout, bounded auth lock, power/effort precedence
- Keywords: scaffolded-backlog, provider auth reliability: probe timeout, bounded auth lock, power/effort precedence, implementation-ready
- Use when: Implementing the scaffolded slice for Provider auth reliability: probe timeout, bounded auth lock, power/effort precedence.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
