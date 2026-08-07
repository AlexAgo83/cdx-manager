## item_053_add_an_opt_in_check_that_mapped_provider_flags_exist_in_the_provider_cli - Add an opt-in check that mapped provider flags exist in the provider CLI
> From version: 0.13.0
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Contract integrity
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- `LAUNCH_PERMISSION_ARGS` and `HEADLESS_CODEX_PERMISSION_ARGS` assert what each provider CLI accepts, and nothing verifies the assertion. GitHub issue #8 was a mapped flag the provider never had, undetected until a user hit it.
- `collect_health_report` checks layout, profiles, state files, and provider CLI versions, but never exercises a flag cdx will actually pass.
- `_provider_capability_hints` returns hardcoded prose about provider capabilities rather than anything observed, so it cannot notice a mapping going stale either.

# Scope
- In:
  - Add a health check that, for each configured provider, asks the installed provider CLI whether the flags cdx maps for each permission are accepted, and reports per provider and permission whether the mapping was confirmed, refused, or could not be determined.
  - Prefer the cheapest interrogation that gives a real answer — reading the CLI's own help or option list where that is authoritative, rather than launching a run.
  - Report a refused flag as a failure, and an indeterminate result as a warning, never as a pass: an unverifiable mapping is the state issue #8 was in.
  - Make the check opt-in behind an explicit flag on `cdx doctor`, since it costs at least one provider CLI invocation per provider, and make its absence visible in the default report rather than silently omitted.
  - Cover the case of a provider with no permission mapping at all, such as ollama, so an empty mapping reads as deliberate rather than as a missing check.
  - Handle a provider CLI that is not installed as indeterminate rather than as a failure.
  - Document the flag in the README alongside the existing doctor documentation.
  - Add tests with a stubbed provider CLI covering: a confirmed mapping, a refused flag, an uninstalled CLI, a provider with no mapping, and the check being absent unless requested.
- Out:
  - No verification at launch time; this is a diagnostic.
  - No automatic correction of a mapping found to be wrong.
  - No probing of provider behavior beyond whether the mapped flags are accepted.
  - No replacement of the existing hardcoded capability hints in this slice.

# Acceptance criteria
- Given a provider CLI that accepts every flag cdx maps for it, the check reports the mapping confirmed for each permission.
- Given a mapped flag the provider CLI rejects, the check reports a failure naming the provider, the permission, and the flag — reproducing the issue #8 condition against a stub.
- Given a provider CLI that is not installed, the check reports indeterminate rather than a failure.
- Given a provider with no permission mapping, the check reports that as deliberate rather than as an unverified mapping.
- Given a default `cdx doctor` run, the check does not execute, and the report makes clear it was not run rather than omitting it silently.
- Given the opt-in flag, the check executes and its findings appear with the existing severity levels.

# AC Traceability
- request-AC5 -> This backlog slice. Proof: Given a provider CLI that accepts every flag cdx maps for it, the check reports the mapping confirmed for each permission.
- request-AC6 -> This backlog slice. Proof: Given a mapped flag the provider CLI rejects, the check reports a failure naming the provider, the permission, and the flag — reproducing the issue #8 condition against a stub.
- request-AC8 -> This backlog slice. Proof: Given a provider CLI that is not installed, the check reports indeterminate rather than a failure.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_014_one_definition_of_what_cdx_accepts_and_emits`
- Architecture decision(s): (none yet)
- Request: `req_024_give_cdx_one_source_of_truth_for_the_values_it_accepts_and_the_provider_flags_it_emits`
- Primary task(s): `task_035_orchestrate_one_source_of_truth_for_accepted_values_and_provider_flags`

# AI Context
- Summary: Add an opt-in check that mapped provider flags exist in the provider CLI
- Keywords: scaffolded-backlog, add an opt-in check that mapped provider flags exist in the provider cli, implementation-ready
- Use when: Implementing the scaffolded slice for Add an opt-in check that mapped provider flags exist in the provider CLI.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
