## item_070_measure_what_a_single_option_actually_costs_before_designing_anything - Measure what a single option actually costs before designing anything
> From version: 0.15.0
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 40%
> Complexity: Low
> Theme: CLI surface
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Owner: claude
> Indicators reviewed: 2026-08-09

# Problem
- Adding `--failover` took five coordinated edits and one was missed, producing a flag that parsed, validated and documented while doing nothing. `--budget`, `--fallback-model` and `--extra-args` each took five to eight files.
- Raw counts are known - `budget` in 7 files, `fallback_model` in 5, `extra_args` in 8, `rtk` in 9, `priority` in 11 - but a count is a symptom, not a diagnosis. Some of those sites are genuine independent decisions, such as how a value is displayed or which provider flag it maps to; others are mechanical restatements of the same fact.
- Designing the consolidation before knowing which is which would repeat a mistake already made in this project: the intuition that `provider_runtime` should split between spec-building and process execution was half wrong once the coupling was actually measured, and only measurement said so.

# Measurement result

Ten candidate declaration sites were checked against five existing options of
different shapes (`rtk` boolean, `budget` and `priority` bounded numbers,
`extra_args` free string, `fallback_model` provider-specific). Each option
touches 8 or 9 of them.

    site                          options   classification
    cli_args: parser table          5/5     restatement - derivable
    cli_args: usage string          5/5     restatement - derivable
    cli_args: unset key list        5/5     restatement - derivable
    session_service: unset allow    5/5     restatement - derivable
    cli_helpers: display list       5/5     restatement - derivable
    commands/status: configs table  5/5     restatement - derivable
    session_service: validation     5/5     INDEPENDENT - the rules differ per option
    cli_helpers: value formatting   3/5     INDEPENDENT - only some need custom rendering
    provider_runtime: mapping       4/5     INDEPENDENT - which provider flag, and whether any

The count is not the finding. Six of the nine sites restate one fact and could
be generated; three encode a decision that has to stay written down. A design
that tried to generate all nine would have to express validation rules and
provider mappings declaratively, which trades one kind of indirection for a
worse one.

**The sharper finding, which the count hid.** Two parsers in the same file
return their results by opposite strategies:

- `_parse_set_args` builds its settings dict by comprehension over a key tuple
  (`src/cli_args.py:272`), so adding an option to the tuple returns it.
- `_parse_run_args` returns an explicit dict literal,every key hand-written.

That is why `--budget`, `--fallback-model` and `--extra-args` never had the
silent-inert failure and `--failover` did: it was added to the run schema and
omitted from the run literal. Verified by extracting both sets - the run schema
declares 14 keys and the returned literal carries all 14 today, `json` aside,
which is consumed as a guard rather than returned.

So the defect this request set out to prevent is not "options are spread over
eight files". It is one function returning by hand what its neighbour derives.
The consolidation should start there, and the generated-site work is a
separate, larger and much less urgent question.

# Scope
- In:
  - Enumerate every declaration site an option touches today, classifying each as an independent decision or a restatement of something already declared.
  - Do it across several existing options of different shapes - a boolean, a bounded number, a free string, a provider-specific one - so the result is not fitted to one case.
  - Publish the measurement in the request as the evidence the design decision rests on, the way `req_027` recorded its coupling table.
  - Name explicitly which sites a single declaration could generate and which it could not.
- Out:
  - Choosing or implementing a consolidation design; that is the next slice and depends on this one.
  - Any change to behaviour, parsing or output.

# Acceptance criteria
- AC1: Every declaration site for at least four existing options is enumerated and classified.
- AC2: The classification distinguishes independent decisions from mechanical restatements, with the reasoning stated per category rather than asserted.
- AC3: The measurement is recorded in the corpus, not only in a commit message, and names what a single declaration could and could not generate.
- AC4: No source behaviour changes in this slice.

# AC Traceability
- request-AC6 -> This backlog slice. Proof: AC1: Every declaration site for at least four existing options is enumerated and classified.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_019_settle_0_15_0_s_remainder`
- Architecture decision(s): (none yet)
- Request: `req_029_settle_what_0_15_0_left_behind_before_cutting_0_15_1`
- Primary task(s): `task_040_settle_0_15_0_s_remainder_and_cut_0_15_1`

# AI Context
- Summary: Measure what a single option actually costs before designing anything
- Keywords: scaffolded-backlog, measure what a single option actually costs before designing anything, implementation-ready
- Use when: Implementing the scaffolded slice for Measure what a single option actually costs before designing anything.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
