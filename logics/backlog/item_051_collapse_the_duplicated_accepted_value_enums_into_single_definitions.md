## item_051_collapse_the_duplicated_accepted_value_enums_into_single_definitions - Collapse the duplicated accepted-value enums into single definitions
> From version: 0.13.0
> Schema version: 1.0
> Status: Done
> Understanding: 100%
> Confidence: 100%
> Progress: 95%
> Complexity: Medium
> Theme: Contract integrity
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- The reasoning-effort values exist in four places and the permission values in two, across `cli_args`, `provider_runtime`, and `session_service`.
- `LAUNCH_POWER_VALUES` and `LAUNCH_REASONING_EFFORT_VALUES` are identical sets defined on consecutive lines of the same module, which is the clearest possible signal that nobody is maintaining them as one thing.
- `cdx schema --json` and its drift test cover only two of the copies, so the schema silently speaks for `cdx run` while presenting itself as the contract for cdx.

# Scope
- In:
  - Choose one module to own each accepted-value set and have every other module import it rather than restate it. Prefer the module that has no dependency on the others, so the ownership does not create an import cycle.
  - Keep any ordering a display surface needs derived from the single definition rather than as a second literal.
  - Point `session_service`'s launch-setting validation at the shared definitions.
  - Extend `cdx schema --json` so it describes the values the whole CLI accepts, distinguishing where a value is accepted by some commands only, if any such case survives this work.
  - Extend the existing schema drift test to cover every validator consuming the shared definitions, so the guard matches the claim the schema makes.
  - Add a check that fails if a second copy of one of these sets is reintroduced, phrased so it names the offending duplicate rather than just failing.
  - Add tests asserting that every value accepted by `cdx run` is accepted by `cdx set` and vice versa, for each of the three settings.
- Out:
  - No new accepted values.
  - No change to how values are normalized once accepted, beyond making the alias handling shared.
  - No renaming of the existing constants beyond what deduplication requires.
  - No changes to provider flag mappings in this slice.

# Acceptance criteria
- Each of the reasoning-effort and permission value sets has exactly one definition in the codebase; the others import it.
- `cdx set` and `cdx run` accept identical value sets for `--permission`, `--power`, and `--reasoning-effort`, asserted by a test that enumerates the shared definition rather than a hand-written list.
- `cdx schema --json` reflects the values the CLI accepts, and its drift test fails if any validator diverges from the published set.
- Reintroducing a duplicate of one of these sets fails a test that names it.
- Every value accepted before this change is still accepted, and the permission aliases still normalize to the same canonical values.
- No import cycle is introduced by the chosen ownership.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: Each of the reasoning-effort and permission value sets has exactly one definition in the codebase; the others import it.
- request-AC3 -> This backlog slice. Proof: `cdx set` and `cdx run` accept identical value sets for `--permission`, `--power`, and `--reasoning-effort`, asserted by a test that enumerates the shared definition rather than a hand-written list.
- request-AC4 -> This backlog slice. Proof: `cdx schema --json` reflects the values the CLI accepts, and its drift test fails if any validator diverges from the published set.
- request-AC7 -> This backlog slice. Proof: Reintroducing a duplicate of one of these sets fails a test that names it.

# Outcome

> Closed retrospectively: the code shipped in the commit named below and the
> proofs were reconstructed from the current code and test suite, not observed
> at the time of delivery.

Shipped in `28fc7a8`. The six duplicated enums collapsed into single
definitions in `src/config.py`: `REASONING_EFFORT_VALUES`,
`PERMISSION_VALUES`, `PERMISSION_ALIASES` and the derived
`PERMISSION_INPUT_VALUES`. Every validator, normalizer and the published
schema read those objects rather than a copy.

Two tests hold the line, both in `test/test_cli_contract_py.py` after today's
test split: `test_every_validator_shares_one_accepted_value_definition`
asserts **identity**, not equality, so a second literal that happens to match
today would still fail; and `test_no_module_restates_an_accepted_value_set`
scans `src/**/*.py` for a restated literal and names the file and line.

The identity assertion matters more than it looks: an equality check would
pass against a fresh copy on the day it was written and only fail later, once
the two drifted - which is exactly the failure this slice existed to remove.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_014_one_definition_of_what_cdx_accepts_and_emits`
- Architecture decision(s): (none yet)
- Request: `req_024_give_cdx_one_source_of_truth_for_the_values_it_accepts_and_the_provider_flags_it_emits`
- Primary task(s): `task_035_orchestrate_one_source_of_truth_for_accepted_values_and_provider_flags`

# AI Context
- Summary: Collapse the duplicated accepted-value enums into single definitions
- Keywords: scaffolded-backlog, collapse the duplicated accepted-value enums into single definitions, implementation-ready
- Use when: Implementing the scaffolded slice for Collapse the duplicated accepted-value enums into single definitions.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
