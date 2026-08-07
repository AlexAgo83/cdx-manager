## item_061_extract_the_status_group_into_its_own_module - Extract the status group into its own module
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
- The status group is the largest separable cluster at 264 lines of entry points and 16 helpers reached only from it, and it is the one a reader most often needs to follow end to end.

# Scope
- In:
  - Move the status entry points and the helpers only they reach into a status module.
  - Keep `session_service` re-exporting every moved name, following the `req_025` facade pattern.
  - Re-measure the group's closure immediately before extracting rather than reusing the number recorded in `item_059`.
  - Run the full suite, and verify the returned dict's keys against a pre-request build.
- Out:
  - No extraction of the backup group in this slice.
  - No change to the status behavior while moving it.

# Acceptance criteria
- The status entry points and their exclusive helpers live in their own module.
- Every name importable from `session_service` before the move is still importable from it.
- The returned dict has the same keys and behavior as before.
- The extraction is its own commit with the full suite passing.
- No caller and no existing test file is changed by the status extraction, and anything the facade could not cover is recorded with its reason.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: The status entry points and their exclusive helpers live in their own module.
- request-AC3 -> This backlog slice. Proof: Every name importable from `session_service` before the move is still importable from it.
- request-AC5 -> This backlog slice. Proof: The returned dict has the same keys and behavior as before.
- request-AC7 -> This backlog slice. Proof: The extraction is its own commit with the full suite passing.
- request-AC8 -> This backlog slice. Proof: No caller and no existing test file is changed by the status extraction, and anything the facade could not cover is recorded with its reason.

# Outcome

Delivered in `7fc239a`. 23 functions and the four status cache constants move
to `src/session_status.py`, which imports nothing from `session_service`.

One test changed, and it is the case AC8 reserves. `_resolve_session_status`
reads `get_cdx_home` and `_get_global_codex_home`, and
`test_codex_status_can_be_derived_from_structured_rollout_rate_limits` patched
both through `src.session_service`. A re-export binds the function, not the
module globals a patch reaches through, so the patch stopped affecting the
call once the function moved - and it failed by returning `None` rather than
by raising, which is the quiet way for this to go wrong. Both targets now name
`src.session_status`.

This was predicted before the extraction by surveying every
`mock.patch("src.session_service.X")` target against the group being moved,
rather than discovered by the failure.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_017_a_session_service_whose_file_boundaries_match_its_real_seams`
- Architecture decision(s): (none yet)
- Request: `req_027_split_session_service_along_the_two_seams_the_coupling_measurement_supports`
- Primary task(s): `task_038_orchestrate_the_measured_session_service_file_split`

# AI Context
- Summary: Extract the status group into its own module
- Keywords: scaffolded-backlog, extract the status group into its own module, implementation-ready
- Use when: Implementing the scaffolded slice for Extract the status group into its own module.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
