# Changelog

## 0.6.5
- Delivered the headless `cdx run --json` contract for Orchestia with explicit-session execution, provider selection, normalized reasoning effort, timeout handling, and stable cdx/provider error envelopes.
- Added run artifacts for headless execution, including absolute transcript, stdout, and stderr paths plus normalized usage fields that remain explicit when token counts are unavailable.
- Hardened session selection, provider routing, status recall, session-scoped authentication, command ergonomics, and update/install release surfaces.
- Validated the release with product tests, Python tests, Logics lint, Logics release gate checks, packaging dry runs, build dry runs, dependency checks, and npm audit.

## 0.1.0 - 0.6.4
- Built the initial multi-session `cdx` CLI, isolated provider profiles, persistent session registry, launch history, shared handoff context, status overview, update flow, installers, checksums, and cross-platform packaging.
