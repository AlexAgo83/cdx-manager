## item_062_extract_the_backup_group_and_record_why_the_other_groups_stay - Extract the backup group and record why the other groups stay
> From version: 0.14.0
> Schema version: 1.0
> Status: Done
> Understanding: 100%
> Confidence: 100%
> Progress: 100%
> Complexity: Medium
> Theme: Maintainability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- The backup group is the second and last seam the measurement supports, at 179 lines and 9 exclusive helpers.
- Once two groups have been extracted, the natural instinct is to finish the job on the other four. Nothing in the code says why that would be wrong, and the measurement that rules it out lives only in a Logics doc.

# Scope
- In:
  - Move the backup entry points and the helpers only they reach into a backup module.
  - Add the facade guard test, so a dropped re-export fails loudly rather than surfacing as an unrelated import error.
  - Record in the code why runtime, auth, crud and settings were left in place, with the exclusive-helper counts that support it.
  - Confirm the end state: the interface unchanged, the facade complete, and the coupling measurement re-run.
- Out:
  - No extraction of the runtime, auth, crud or settings groups.
  - No new abstraction over the modules that now exist.

# Acceptance criteria
- The backup entry points and their exclusive helpers live in their own module.
- A guard test fails when the facade stops exposing a name its callers import, verified by removing one.
- The reason the remaining groups were not split is stated where a reader of the code will find it, with the counts behind it.
- The extraction is its own commit with the full suite passing.
- No caller and no existing test file is changed by the backup extraction, and anything the facade could not cover is recorded with its reason.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: The backup entry points and their exclusive helpers live in their own module.
- request-AC4 -> This backlog slice. Proof: A guard test fails when the facade stops exposing a name its callers import, verified by removing one.
- request-AC6 -> This backlog slice. Proof: The reason the remaining groups were not split is stated where a reader of the code will find it, with the counts behind it.
- request-AC7 -> This backlog slice. Proof: The extraction is its own commit with the full suite passing.
- request-AC8 -> This backlog slice. Proof: No caller and no existing test file is changed by the backup extraction, and anything the facade could not cover is recorded with its reason.

# Outcome

Delivered in `672df87`. 11 functions and one constant move to
`src/session_backup.py`. No test changed:
`mock.patch("src.session_service.shutil")` still bites because `shutil` is one
module object shared across modules and `session_service` still imports it.

The coupling table now lives in `session_service`'s module docstring, not only
in `item_059`. `test_only_the_measured_seams_were_split_out` fails if
`src/session_runtime.py` or `src/session_auth.py` appears, or if the reasoning
is deleted.

The facade guard test is deliberately stronger than the `cli_commands` one it
follows. That version scanned import statements only, which would have caught
**neither** failure this split produced - both were `mock.patch` string
targets, where a dropped re-export makes the patch a silent no-op instead of
an error. This one checks patch targets too, and was verified by removing a
single re-export: it fails and names the file and line.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_017_a_session_service_whose_file_boundaries_match_its_real_seams`
- Architecture decision(s): (none yet)
- Request: `req_027_split_session_service_along_the_two_seams_the_coupling_measurement_supports`
- Primary task(s): `task_038_orchestrate_the_measured_session_service_file_split`

# AI Context
- Summary: Extract the backup group and record why the other groups stay
- Keywords: scaffolded-backlog, extract the backup group and record why the other groups stay, implementation-ready
- Use when: Implementing the scaffolded slice for Extract the backup group and record why the other groups stay.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
