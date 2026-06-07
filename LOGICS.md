# Logics Context

This repository uses the Logics workflow to keep product intent, backlog scope, implementation tasks, and architectural decisions connected to the code that ships in `cdx-manager`.

## Operating Rule

- Treat `logics/` as managed workflow context, not scratch notes.
- Keep workflow documents in English.
- Prefer `logics-manager` for Logics operations when it is available.
- Use raw file edits only when the needed change is editorial, cross-document, or not covered by a `logics-manager flow ...` command.
- Keep Logics updates small enough to review, but do not leave delivered work in `Ready` or `In progress`.

## Document Map

- `logics/request`: incoming needs, user requests, or integration asks.
- `logics/backlog`: scoped delivery slices with acceptance criteria, priority, and links back to requests.
- `logics/tasks`: execution plans and closeout evidence derived from backlog items.
- `logics/specs`: lightweight functional specs derived from requests or tasks.
- `logics/product`: product framing, user value, non-goals, and success signals.
- `logics/architecture`: ADRs and technical decisions.
- `logics/external`: generated artifacts that do not fit the managed doc folders.

## Required Links

- A request with acceptance criteria should link at least one backlog item under `# Backlog`.
- A backlog item should link its source request and primary task under `# Links`.
- A task should link its source backlog and related request under `# Backlog` and `# Links`.
- Backlog/task docs that make a meaningful product claim should link a product brief.
- Backlog/task docs that define runtime boundaries, persistence, security, provider behavior, JSON contracts, or launch semantics should link an ADR.
- Product briefs and ADRs should mirror their related managed docs under `# References`, not only in front-matter prose.

## Status Discipline

- `Draft`: incomplete idea or rough capture.
- `Ready`: scoped and actionable but not yet implemented.
- `In progress`: actively being implemented.
- `Blocked`: cannot proceed without a named dependency or decision.
- `Done`: delivered, validated, and traceability updated.
- `Obsolete` or `Archived`: no longer active; explain why in the report or notes.

Do not leave a request as `Ready` after its code and release notes have shipped. Promote it, link the delivery docs, and close the chain.

## Acceptance Traceability

For each request/backlog/task chain:

- Request ACs should map to backlog slices using `request-ACN -> ...` lines in backlog docs.
- Request ACs should map to implementation tasks when the work is delivered.
- Backlog ACs should map to task plan items or report evidence.
- Proof should name the command, file, behavior, or validation result that satisfies the AC.
- Avoid placeholder refs such as `req_XXX_example` in active docs. Replace them with real refs or `(none yet)` if no source exists.

## Closeout Rules

Before marking a task `Done`:

- Check every DoD item.
- Record validation evidence under `# Validation` or `# Report`.
- Update linked request/backlog/task docs.
- Keep `Progress: 100%`.
- Run the relevant local validation, at minimum `logics-manager lint --require-status` for Logics-only changes.

Before release prep:

- Run `logics-manager status`.
- Run `logics-manager health`.
- Run `logics-manager audit`.
- Run `npm run release:validate` before any registry publication.
- Generate archive checksums with `python3 scripts/update_release_checksums.py --tag vX.Y.Z` once GitHub tag archives exist, commit `checksums/release-archives.json` to `main`, and only publish the GitHub release after the checksum gate passes for the same tag/version.
- If the full audit intentionally excludes legacy docs, state the legacy cutoff or scoped audit command in the release notes.

## Preferred Commands

Use these direct commands when `logics-manager` is on `PATH`:

- `logics-manager status`: summarize open workflow state and next actions.
- `logics-manager health`: count docs, workflow docs, open docs, and issue signals.
- `logics-manager audit`: check workflow consistency, gates, companion docs, and traceability.
- `logics-manager lint --require-status`: validate document structure and required status fields.
- `logics-manager view`: open the browser viewer for visual navigation and focus workflows.
- `cdx view`: open the same viewer through cdx when `logics-manager` is installed; use `cdx view --json` for diagnostics without launching a browser.
- `logics-manager sync list-docs`: list bounded document context.
- `logics-manager sync read-doc <ref-or-path>`: read one managed document.
- `logics-manager sync search-docs <query>`: search the corpus without broad file scans.
- `logics-manager sync context-pack ...`: build bounded context packs for implementation or review.
- `logics-manager flow list`: inspect active request/backlog/task docs.
- `logics-manager flow new <request|backlog|task>`: create a managed workflow doc.
- `logics-manager flow promote request-to-backlog <request-ref>`: create a linked backlog item.
- `logics-manager flow promote backlog-to-task <backlog-ref>`: create a linked task.
- `logics-manager flow companion <product|architecture>`: create companion framing docs.
- `logics-manager flow repair <gates|ac-traceability|links|mermaid>`: apply deterministic workflow repairs.
- `logics-manager flow validate-closeout <task-ref>`: preflight a task before closing.
- `logics-manager flow closeout <task-ref> --validation "<evidence>" --lint --audit`: close a task with evidence when the command fits.
- `logics-manager mcp tools`: inspect Logics MCP surfaces when an MCP workflow is the right fit.

If the executable is not on `PATH`, use the Python module form:

- `python3 -m logics_manager status`
- `python3 -m logics_manager health`
- `python3 -m logics_manager audit`
- `python3 -m logics_manager lint --require-status`
- `python3 -m logics_manager flow ...`

## Assistant CLI Hygiene

- If `rtk` is available, prefer RTK wrappers for noisy terminal commands whose exact raw output is not required.
- Keep raw commands for exact diffs, complete logs, snapshots, security-sensitive inspection, machine-readable JSON, or any case where RTK filtering could hide relevant detail.
- In cdx sessions, `cdx set <session> --rtk on` stores the RTK preference and injects it into assistant launch prompts.
- In cdx sessions, Logics guidance is auto-enabled when `logics-manager` is available; `cdx set <session> --logics off` disables it for a noisy or unrelated session.

## Repository Validation

Use the validation set that matches the changed surface:

- Logics-only: `logics-manager lint --require-status`, plus `logics-manager audit` when changing request/backlog/task links.
- CLI behavior: `npm run lint`, `npm test`, and focused `python -m unittest discover -s test -p 'test_*_py.py' -k <pattern>` when appropriate.
- Release prep: `npm run release:validate`, version checks, package checks, Logics validation, `git diff --check`, and the release checklist in the relevant changelog.

## Maintenance Notes

- Do not vendor `logics/skills/` into this repository; Logics tooling comes from the installed `logics-manager` package.
- Do not commit local cache files under `logics/.cache/`.
- Remove macOS artifacts such as `.DS_Store` when found under `logics/`.
- Keep generated mermaid diagrams valid when editing managed docs.
