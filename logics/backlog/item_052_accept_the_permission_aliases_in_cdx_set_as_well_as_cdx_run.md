## item_052_accept_the_permission_aliases_in_cdx_set_as_well_as_cdx_run - Accept the permission aliases in cdx set as well as cdx run
> From version: 0.13.0
> Schema version: 1.0
> Status: Done
> Understanding: 100%
> Confidence: 100%
> Progress: 100%
> Complexity: Low
> Theme: Contract integrity
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- `cdx run --permission workspace-write` is accepted and normalized to `default`; `cdx set <name> --permission workspace-write` fails with `Unsupported permission: workspace-write`.
- The same asymmetry applies to `read-only` and `danger-full-access`, which are the provider-native spellings a user is most likely to have in hand.
- `cdx schema --json` publishes the aliases without saying they apply to one command only, so following the schema produces a rejection.

# Scope
- In:
  - Apply the same alias normalization in `cdx set` (and any other launch-setting entry point such as the `perm` alias command) that `cdx run` already performs.
  - Store the canonical value, not the alias, so persisted session state stays in the canonical vocabulary and nothing downstream has to learn the aliases.
  - Confirm the direction: aliases are added to `set` rather than removed from `run`, because removing them would break callers that pass provider-native spellings today.
  - Make the error message for a genuinely unsupported permission list the accepted values including aliases, consistent with how `cdx run` already reports it.
  - Document in the README that the aliases work wherever a permission is accepted.
  - Add tests for each alias through `cdx set` and through the `perm` alias command, asserting the stored value is the canonical form.
- Out:
  - No removal of the aliases from `cdx run`.
  - No new aliases beyond the three that already exist.
  - No aliasing for power or reasoning effort, which have no alternative spellings.

# Acceptance criteria
- Given `cdx set <name> --permission workspace-write`, the command succeeds and the session stores `default`.
- Given `read-only` and `danger-full-access` through `cdx set`, they store `review` and `full` respectively.
- Given the same aliases through the `perm` alias command, the behavior matches `cdx set`.
- Given a genuinely unsupported permission, the error lists the accepted values including the aliases.
- Given a canonical value through `cdx set`, behavior is unchanged from today.
- Reading back a session configured through an alias shows the canonical value, so nothing downstream needs to know aliases exist.

# AC Traceability
- request-AC2 -> This backlog slice. Proof: Given `cdx set <name> --permission workspace-write`, the command succeeds and the session stores `default`.
- request-AC7 -> This backlog slice. Proof: Given `read-only` and `danger-full-access` through `cdx set`, they store `review` and `full` respectively.
- request-AC8 -> This backlog slice. Proof: Given the same aliases through the `perm` alias command, the behavior matches `cdx set`.

# Outcome

> Closed retrospectively: the code shipped in the commit named below and the
> proofs were reconstructed from the current code and test suite, not observed
> at the time of delivery.

Shipped in `28fc7a8`. `cdx set` now accepts the provider-native permission
aliases that `cdx run` already took, and stores the canonical form:
`workspace-write` -> `default`, `read-only` -> `review`,
`danger-full-access` -> `full`.

The decision recorded when this was scoped was honoured rather than quietly
reversed: the aliases were **added to `set`** instead of removed from `run`,
because removing them would break callers that pass the provider spellings
today.

`test_set_and_run_accept_the_same_values` in
`test/test_commands_settings_py.py` iterates `PERMISSION_INPUT_VALUES` and
asserts both entry points normalize each value identically, so the asymmetry
cannot come back one value at a time.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_014_one_definition_of_what_cdx_accepts_and_emits`
- Architecture decision(s): (none yet)
- Request: `req_024_give_cdx_one_source_of_truth_for_the_values_it_accepts_and_the_provider_flags_it_emits`
- Primary task(s): `task_035_orchestrate_one_source_of_truth_for_accepted_values_and_provider_flags`

# AI Context
- Summary: Accept the permission aliases in cdx set as well as cdx run
- Keywords: scaffolded-backlog, accept the permission aliases in cdx set as well as cdx run, implementation-ready
- Use when: Implementing the scaffolded slice for Accept the permission aliases in cdx set as well as cdx run.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
