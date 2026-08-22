# Codex Context

This file defines the working context for Codex in this repository.

## Workflow

Use the canonical `logics-manager` CLI to create, promote, start, and finish Logics docs:

- `python3 -m logics_manager flow new request --title "..."`
- `python3 -m logics_manager flow promote request-to-backlog logics/request/req_NNN_*.md`
- `python3 -m logics_manager flow start logics/tasks/task_NNN_*.md --owner "$LOGICS_AGENT"`
- `python3 -m logics_manager flow progress task logics/tasks/task_NNN_*.md --progress <n>%`
- `python3 -m logics_manager flow finish task logics/tasks/task_NNN_*.md`
- `python3 -m logics_manager lint --require-status`
- `python3 -m logics_manager audit --legacy-cutoff-version 1.1.0 --group-by-doc`

Operational runbooks live in `logics/runbook/` (`run_*.md`, Draft/Active/Archived). Before repeating an investigation or operational procedure, check for a matching one with `logics-manager sync search-docs --kind runbook "<symptom or task>"`; record a new one with `logics-manager flow companion runbook --title "..."` once you have verified it is reusable.

Bundled agent skills (e.g. `/corpus` for scaffolding a full request chain) can be installed once per machine with `logics-manager skills install`.

When naming a Logics document in a response, give its viewer link too if one is running for this repository: `read_logics_doc` and the CLI's `flow show`/`sync list-docs`/`sync search-docs` already carry it, so this usually means passing along what they returned rather than building a link by hand. The address always comes from the running viewer, never a guessed default port; see `docs/cli.md` for the URL grammar.

Claude runtime artifacts are generated outside the repository from the integrated runtime.
Do not edit generated runtime artifacts by hand unless you are deliberately repairing a generated artifact.

Do not edit indicator lines, owner assignments, or workflow links by hand.
Not every fix needs a chain. ADR 030 decides which do: a fix needs one when its reasoning cannot live at the point where it would be undone -- it changes what the product asserts, trades one claim against another, rests on a measurement, or has a cause spanning layers. Otherwise the comment at that declaration and a test that fails without it are the record. Say which side a fix falls on when you fix it, not afterwards.
During task execution, treat meaningful waves as ADR 009 checkpoints: update affected Logics docs inside the wave and leave the repo commit-ready; actual commits stay under operator control.
When grooming or creating backlog items, set a deliberate `# Priority` tier (`High`, `Medium`, or `Low`) with a one-line rationale instead of leaving the default unreviewed.
Sequence delivery plans and roadmaps by status priority order before lower-priority work when dependencies allow.
When delivery consumes a linked product brief, `flow closeout` should settle it; otherwise set the brief to `Settled` or `Superseded` through the CLI instead of leaving it `Proposed`.
When `rtk` is available, prefer it for noisy commands. Use raw commands or `rtk proxy <cmd>` when exact output or one-off command semantics matter.
For targeted npm binaries, prefer `rtk npm exec -- vitest ...` instead of `rtk npx vitest ...`.
