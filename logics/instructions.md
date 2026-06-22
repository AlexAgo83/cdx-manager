# Codex Context

This file defines the working context for Codex in this repository.

## Workflow

Use the canonical `logics-manager` CLI to create, promote, and finish Logics docs:

- `python3 -m logics_manager flow new request --title "..."`
- `python3 -m logics_manager flow promote request-to-backlog logics/request/req_NNN_*.md`
- `python3 -m logics_manager flow finish task logics/tasks/task_NNN_*.md`
- `python3 -m logics_manager lint --require-status`
- `python3 -m logics_manager audit --legacy-cutoff-version 1.1.0 --group-by-doc`

Claude runtime artifacts are generated outside the repository from the integrated runtime.
Do not edit generated runtime artifacts by hand unless you are deliberately repairing a generated artifact.

Do not edit indicator lines or workflow links by hand.
