## item_059_decide_the_file_split_from_the_seams_the_decomposition_exposed - Decide the file split from the seams the decomposition exposed
> From version: 0.14.0
> Schema version: 1.0
> Status: Done
> Understanding: 100%
> Confidence: 100%
> Progress: 100%
> Complexity: Low
> Theme: Maintainability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- The obvious instinct is to split the file by the concern clusters, but those clusters were inferred from closure names before the dependencies were made explicit.
- Deciding the seam now would repeat the mistake this request exists to avoid: cutting a file whose parts are not yet separable.

# Scope
- In:
  - Once the closures are functions, measure the real coupling between the concern groups the same way it was measured for the command file: how many helpers each group uses exclusively, and how many are shared.
  - Decide from that measurement whether to split the file at all, and if so along which seam.
  - Record the decision and its evidence, including the case for leaving the file whole if the measurement does not support cutting it.
  - If a split is warranted, scope it as its own request rather than folding it in here.
- Out:
  - No split performed in this slice.
  - No decision made before the decomposition is complete.

# Acceptance criteria
- The coupling between concern groups is measured, not estimated, using the same method applied to the command file.
- A decision is recorded with the measurement that supports it.
- If the measurement does not support a split, that outcome is recorded as the answer rather than treated as a failure.
- Any split that is warranted is scoped as a separate request.

# Measurement

Taken the same way as for the command file: transitive closure from each
group's entry points, so a helper reached only through another helper counts
against the group that reaches it.

| group | entries | entry lines | exclusive helpers | excl. lines | shared |
|---|---|---|---|---|---|
| status | 7 | 264 | 16 | 217 | 7 |
| backup | 2 | 179 | 9 | 125 | 7 |
| crud | 12 | 235 | 3 | 36 | 8 |
| settings | 2 | 58 | 1 | 85 | 1 |
| runtime | 6 | 115 | 0 | 0 | 3 |
| auth | 1 | 10 | 0 | 0 | 1 |

40 helpers: 29 exclusive to one group, 10 shared, 1 reached from no entry
point (`_parse_status_timeout_seconds`, used by the factory itself).

The shared ten are small and mostly incidental: `_local_now_iso` (2 lines) is
used by all six groups, and `_encode`, `_get_session_root`,
`_get_session_auth_home`, `_ensure_private_dir` are path and formatting
utilities rather than domain logic.

# Decision

**Split, but along two seams only, and as a separate request.**

The measurement does not support the six-way split the concern clusters
suggested, which is exactly the assumption this slice existed to test:

- `status` (481 lines, 16 exclusive helpers) and `backup` (304 lines, 9
  exclusive helpers) are genuinely self-contained. These are the two seams.
- `runtime` (115 lines) and `auth` (10 lines) have **zero** exclusive
  helpers - everything they touch is shared. Made into files they would be
  thin wrappers over imports from elsewhere, which is worse than leaving them
  in place.
- `crud` is the core the others depend on and stays as the base module.
- The ten shared helpers need a utility layer first, or the two new modules
  will import back from the module they were cut out of.

# What this slice already achieved without any split

The problem the request named was not the file length, it was that
`create_session_service` was 1153 lines. That is gone: the factory is **56
lines** and holds no closures at all, and the module is 71 flat functions with
a median length of 12 lines and a largest of 121. The file is 1690 lines, but
a 1690-line file of 12-line functions is a different object from a 1652-line
file with a 1153-line function in it.

So the split is worth doing but is no longer urgent, which is the honest
reason to scope it separately rather than fold it in here.

# AC Traceability
- request-AC6 -> This backlog slice. Proof: The coupling between concern groups is measured, not estimated, using the same method applied to the command file.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_016_a_session_service_that_can_be_read_in_pieces`
- Architecture decision(s): (none yet)
- Request: `req_026_break_up_the_1153_line_session_service_factory_before_splitting_its_file`
- Primary task(s): `task_037_orchestrate_the_session_service_decomposition`

# AI Context
- Summary: Decide the file split from the seams the decomposition exposed
- Keywords: scaffolded-backlog, decide the file split from the seams the decomposition exposed, implementation-ready
- Use when: Implementing the scaffolded slice for Decide the file split from the seams the decomposition exposed.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Low
- Rationale: Set by scaffold input or defaulted for grooming.
