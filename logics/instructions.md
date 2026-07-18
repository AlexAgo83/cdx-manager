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

Bundled agent skills (e.g. `/corpus` for scaffolding a full request chain) can be installed once per machine with `logics-manager skills install`.

Claude runtime artifacts are generated outside the repository from the integrated runtime.
Do not edit generated runtime artifacts by hand unless you are deliberately repairing a generated artifact.

Do not edit indicator lines, owner assignments, or workflow links by hand.
During task execution, treat meaningful waves as ADR 009 checkpoints: update affected Logics docs inside the wave and leave the repo commit-ready; actual commits stay under operator control.
When grooming or creating backlog items, set a deliberate `# Priority` tier (`High`, `Medium`, or `Low`) with a one-line rationale instead of leaving the default unreviewed.
Sequence delivery plans and roadmaps by status priority order before lower-priority work when dependencies allow.
When delivery consumes a linked product brief, `flow closeout` should settle it; otherwise set the brief to `Settled` or `Superseded` through the CLI instead of leaving it `Proposed`.
