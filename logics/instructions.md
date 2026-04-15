# Codex Context

This file defines the working context for Codex in this repository.

## Language

Use English for all communication, code comments, and documentation.

## Workflow

The `logics` folder defines a lightweight product flow:

* `logics/architecture`: Architecture notes, decisions, and diagrams.
* `logics/product`: Product briefs and product decision framing docs.
* `logics/request`: Incoming requests or ideas (problem statement + context).
* `logics/backlog`: Scoped items with acceptance criteria + priority.
* `logics/tasks`: Execution plans derived from backlog items (plan + progress + validation).
* `logics/specs`: Lightweight functional specs derived from backlog/tasks.
* `logics/external`: Generated artifacts (images, exports) that don't fit other logics folders.

## Indicators

Use the following indicators in request/backlog/task items:

* `From version: X.X.X` : The version when the need was first identified.
* `Understanding: ??%` : Your estimated understanding of the need.
* `Confidence: ??%` : Your confidence in solving the need.
* `Progress: ??%` : Your progress toward completing the backlog item or task.
* `Complexity: Low | Medium | High` : Effort/complexity classification.
* `Theme: Combat | Items | Economy | UI | ...` : High-level theme/epic tag.
* `Status: Draft | Ready | In progress | Blocked | Done | Obsolete | Archived` : Workflow maturity for requests, backlog items, and tasks.

Use the following indicators in product briefs:

* `Date: YYYY-MM-DD` : The last meaningful framing date for this brief.
* `Status: Draft | Proposed | Active | Validated | Rejected | Superseded | Archived` : Product maturity of the brief.
* `Related request:` : Primary linked request ref when available.
* `Related backlog:` : Primary linked backlog ref when available.
* `Related task:` : Primary linked task ref when available.
* `Related architecture:` : Linked ADR ref when the product framing depends on a technical decision.
* `Reminder:` : Short maintenance instruction to keep the brief current.
* Keep linked managed docs mirrored under `# References` as backticked relative paths, not only in indicator prose.

Use the following indicators in architecture docs:

* `Date: YYYY-MM-DD` : The date of the current ADR revision.
* `Status: Draft | Proposed | Accepted | Rejected | Superseded | Archived` : Decision state.
* `Drivers:` : Main technical or operational drivers behind the decision.
* `Related request:` : Primary linked request ref when available.
* `Related backlog:` : Primary linked backlog ref when available.
* `Related task:` : Primary linked task ref when available.
* `Reminder:` : Short maintenance instruction to keep the ADR current.
* Keep linked managed docs mirrored under `# References` as backticked relative paths, not only in indicator prose.

## Automation

This repository uses a reusable Logics skills kit (usually imported as a submodule under `logics/skills/`).
Canonical examples use `python ...`; if your environment only exposes `python3` or `py -3`, use that equivalent launcher instead.

- Create/promote request/backlog/task docs: `python logics/skills/logics.py flow ...`
- Lint Logics docs: `python logics/skills/logics.py lint --require-status`
- Bootstrap folders (this script): `python logics/skills/logics.py bootstrap`

## MCP

Available MCP skills include:

- Chrome DevTools: `logics/skills/logics-mcp-chrome-devtools/SKILL.md`
- Terminal: `logics/skills/logics-mcp-terminal/SKILL.md`
- Figma: `logics/skills/logics-mcp-figma/SKILL.md`
- Linear: `logics/skills/logics-mcp-linear/SKILL.md`
- Notion: `logics/skills/logics-mcp-notion/SKILL.md`

## Validation

Project validation commands are project-specific.
Add the relevant ones to task docs under `# Validation` (tests/lint/build/typecheck).
