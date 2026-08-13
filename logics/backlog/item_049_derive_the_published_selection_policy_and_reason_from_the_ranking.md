## item_049_derive_the_published_selection_policy_and_reason_from_the_ranking - Derive the published selection policy and reason from the ranking
> From version: 0.13.0
> Schema version: 1.0
> Status: Done
> Understanding: 100%
> Confidence: 100%
> Progress: 100%
> Complexity: Medium
> Theme: Session selection
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- `policy` and `reason` in `handle_select` are literals that were accurate at some point and are not now. The published policy omits the reasoning-effort tie-break and presents the readiness filter as a sort stage.
- `reason` claims availability decided the outcome even when priority, reasoning effort, or the alphabetical fallback did.
- Nothing fails when the sort key changes and the strings do not, which is exactly how they came to be wrong.

# Scope
- In:
  - Name the ranking's ordered factors in one place and build both the sort key and the published `selection_policy` from that single definition.
  - Describe candidate filtering separately from ordering in the payload, since readiness excludes candidates rather than ordering them.
  - Have the ranking report which factor first separated the winner from the runner-up, and use that for `reason`.
  - Handle the single-candidate case explicitly: with nothing to compare against, `reason` should say so rather than name an arbitrary factor.
  - Add a test that fails if the sort key and the published policy can disagree, in the spirit of the existing schema drift test.
  - Document both fields in the README's programmatic-caller section.
- Out:
  - No change to the ranking or to which session is selected.
  - No stable enumerated policy identifier.
  - No reporting of the full ranked list.

# Acceptance criteria
- Given any selection, the published `selection_policy` lists exactly the factors the sort key uses, in the same order.
- Given a winner settled by `--priority` rather than availability, `reason` names priority.
- Given a winner settled by availability, `reason` names availability, matching today's message for that case.
- Given exactly one candidate, `reason` reports that it was the only candidate rather than naming a deciding factor.
- Given a change to the ordered factor list, a test fails unless the published policy changes with it.
- Given the same sessions and status rows as before this change, the selected session is identical.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: Given any selection, the published `selection_policy` lists exactly the factors the sort key uses, in the same order.
- request-AC2 -> This backlog slice. Proof: Given a winner settled by `--priority` rather than availability, `reason` names priority.
- request-AC6 -> This backlog slice. Proof: Given a winner settled by availability, `reason` names availability, matching today's message for that case.
- request-AC7 -> This backlog slice. Proof: Given exactly one candidate, `reason` reports that it was the only candidate rather than naming a deciding factor.

# Outcome

> Closed retrospectively: the code shipped in the commit named below and the
> proofs were reconstructed from the current code and test suite, not observed
> at the time of delivery.

Shipped in `9a05308`. `selection_policy()` is **built from** `RANKING_FACTORS`
rather than written by hand, so changing the sort order changes what
`cdx select` publishes without anyone remembering to edit a string. Its
docstring records what the hand-written version had drifted into: it omitted
the reasoning-effort tie-break entirely and described a candidate filter as a
sort stage.

`deciding_factor()` names the factor that actually separated the winner from
the runner-up for that specific call, replacing the fixed sentence.
`test_single_candidate_reports_no_deciding_factor` pins the honest answer in
the case where nothing decided it, which is the case a fixed sentence gets
wrong most confidently.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_013_truthful_reporting_of_how_a_session_was_selected`
- Architecture decision(s): (none yet)
- Request: `req_023_stop_cdx_select_from_publishing_a_selection_policy_and_reason_it_does_not_follow`
- Primary task(s): `task_034_orchestrate_truthful_selection_reporting`

# AI Context
- Summary: Derive the published selection policy and reason from the ranking
- Keywords: scaffolded-backlog, derive the published selection policy and reason from the ranking, implementation-ready
- Use when: Implementing the scaffolded slice for Derive the published selection policy and reason from the ranking.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
