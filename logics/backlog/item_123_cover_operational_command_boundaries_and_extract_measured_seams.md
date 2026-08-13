## item_123_cover_operational_command_boundaries_and_extract_measured_seams - Cover operational command boundaries and extract measured seams
> From version: 0.19.1
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 85%
> Complexity: High
> Theme: Maintainability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-13 22:09:02

# AI Context
- Summary: Add tests at operational boundaries before extracting only demonstrated module seams.
- Keywords: cover, operational, command, boundaries, extract, measured, seams
- Use when: Touching tray/context commands, provider runtime, or CLI argument parsing.
- Skip when: Proposing a generic command framework or rewrite.

# Problem
- commands/tray.py and commands/context_memory.py each measured 43% coverage during review.
- provider_runtime.py and cli_args.py centralise unrelated branches across more than one thousand lines each.

# Scope
- In:
  - Add small focused tests for process, platform, persistence, stdin, and error branches identified by coverage.
  - Extract only existing provider/auth/launch and command-family seams while preserving imports and public CLI behaviour.
  - Keep the change dependency-free and avoid new abstraction layers.
- Out:
  - A full CLI rewrite.
  - Raising coverage through unverified superficial tests.

# Acceptance criteria
- New tests execute the identified tray and context-memory operational branches.
- Each extraction has focused regression coverage and preserves CLI output and error contracts.
- No new runtime dependency or generic command framework is introduced.

# AC Traceability
- request-AC7 -> This backlog slice. Proof: New tests execute the identified tray and context-memory operational branches.
- request-AC8 -> This backlog slice. Proof: Each extraction has focused regression coverage and preserves CLI output and error contracts.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_047_reliable_delivery_and_runtime_contracts`
- Architecture decision(s): (none yet)
- Request: `req_061_harden_repository_reliability_release_verification_and_cli_contracts`
- Primary task(s): `task_071_orchestrate_repository_reliability_and_release_contract_hardening`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
