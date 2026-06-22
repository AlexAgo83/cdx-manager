# Logics Local Assistant Bridge

<!-- logics-manager:managed:start -->
This local file is refreshed by `logics-manager bootstrap`.
Canonical generated instructions live in `logics/instructions.md`.
If unmanaged notes in this file conflict with this section, follow this managed section.

Core rules:
- Read `logics/instructions.md` before editing workflow docs.
- Run `logics-manager bootstrap` after updating Logics Manager to refresh this bridge.
- Use `logics-manager --help` and subcommand `--help` for the current CLI contract.
- Do not hand-edit Logics indicators, lineage links, Mermaid signatures, or done status.

Inspection and validation:
- Use `logics-manager status` for the next work signal.
- Use `logics-manager health` for corpus-level anomalies.
- Run `logics-manager lint --require-status` and `logics-manager audit --group-by-doc` after workflow edits.

Bounded context:
- Use `logics-manager sync read-doc <ref> --max-chars <n>` before opening large docs directly.
- Use `logics-manager sync list-docs`, `search-docs`, and `context-pack` for bounded discovery.

Workflow lifecycle:
- Use `logics-manager flow new|promote|closeout|finish` for request, backlog, and task lifecycle changes.
- Use `logics-manager flow finish task <path>` instead of setting `Status: Done` manually.
- Use `logics-manager sync refresh-mermaid-signatures` after editing Mermaid diagrams.

Release workflow:
- Use `logics-manager release status` before claiming release readiness.
- Use `logics-manager release plan <version>` and `logics-manager release validate <version>` for release checks.
- Record release proof with `logics-manager release evidence add ...`.
- Do not treat conversation memory or a successful command without matching evidence as release-ready proof.

Viewer and MCP:
- Use `logics-manager view` for the browser viewer and focus workflows.
- Use `logics-manager mcp ...` only when an MCP client surface is the right fit.

Document hygiene:
- Keep paths in Logics docs repo-relative, never absolute filesystem paths.
- Keep Mermaid labels plain ASCII, short, and free of raw route braces or inline code.
<!-- logics-manager:managed:end -->
