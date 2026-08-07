## req_027_split_session_service_along_the_two_seams_the_coupling_measurement_supports - Split session_service along the two seams the coupling measurement supports
> From version: 0.14.0
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Maintainability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# Needs
- `req_026` removed the reason `src/session_service.py` could not be split: `create_session_service` is 56 lines and holds no closures, and the module is 71 flat functions with a median length of 12 lines. The file is still 1690 lines.
- `item_059` measured the coupling between concern groups and found two real seams and four false ones. Acting on that measurement is what this request is for; it exists so the measurement is used rather than filed.
- The status group is 264 lines of entry points with 16 helpers reached only from it, and the backup group is 179 lines with 9. Those two are separable today.
- The runtime and auth groups have zero exclusive helpers between them. Made into files they would be thin wrappers over imports from the module they came from, which reads worse than leaving them where they are.

# Context
- The coupling table is recorded in `item_059_decide_the_file_split_from_the_seams_the_decomposition_exposed`. It was taken as a transitive closure from each group's entry points, not as direct calls, because a helper reached only through another helper still has to move with the group that reaches it.
- Ten helpers are shared across groups. Six of them are small utilities: `_local_now_iso` (2 lines) is used by all six groups, and `_encode`, `_get_session_root`, `_get_session_auth_home`, `_ensure_private_dir` are path and formatting helpers rather than domain logic.
- `req_025` established the pattern this request should follow: extract to a package, keep the original module as a facade that re-exports every name its callers import, and prove the facade with a guard test. `test_cli_commands_facade_still_exposes_every_name_its_callers_import` is the working example.
- That request also produced the failure modes to expect. A pass-through import gets stripped by ruff once its last in-file caller leaves, and function-local relative imports resolve one package level too shallow once inside a subpackage.
- `src/session_service.py` is imported by `src/cli.py` via `create_session_service`, and `test/test_session_service_py.py` (2055 lines) plus `test/test_session_service_helpers_py.py` exercise it. Those tests are the regression net.
- The service interface is the dict `create_session_service` returns: 29 keys, bound with `functools.partial`. It must not change, exactly as in `req_026`.

# Acceptance criteria
- AC1: The status group and the backup group each live in their own module, with the helpers reached only from that group alongside them.
- AC2: The shared helpers are relocated to a utility layer before either extraction, so neither new module imports back from the module it was cut out of.
- AC3: `session_service` remains the import location for every name its callers import today, including `create_session_service` and any helper the tests import directly.
- AC4: A guard test fails if the facade stops exposing a name its callers import, following the one `req_025` added for `cli_commands`.
- AC5: The service interface is unchanged: the returned dict has the same 29 keys and the same behavior, verified against a pre-request build.
- AC6: The runtime, auth, crud and settings groups are not made into files. The measurement that rules the first two out is restated in the code or the commit, so a later reader does not redo the split by instinct.
- AC7: Each extraction is its own commit with the full suite passing, so a regression is attributable to one group.
- AC8: No caller and no existing test file is changed by the split, aside from anything the facade genuinely cannot cover, and any such case is recorded.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_017_a_session_service_whose_file_boundaries_match_its_real_seams`
- Architecture decision(s): (none yet)

# References
- src/session_service.py
- src/cli_helpers.py
- src/commands/__init__.py
- test/test_session_service_py.py
- test/test_session_service_helpers_py.py

# AI Context
- Summary: Split session_service along the two seams the coupling measurement supports
- Keywords: request-chain-scaffold, split session_service along the two seams the coupling measurement supports, development-ready
- Use when: You need to implement or review the scaffolded workflow for Split session_service along the two seams the coupling measurement supports.
- Skip when: The change is unrelated to this scaffolded request chain.

# Backlog
- `item_060_move_the_shared_helpers_into_a_session_service_utility_layer`
- `item_061_extract_the_status_group_into_its_own_module`
- `item_062_extract_the_backup_group_and_record_why_the_other_groups_stay`
