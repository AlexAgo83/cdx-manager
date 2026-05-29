# Code Structure Review

_Generated: 2026-05-29 12:56 UTC_

## Detected stack (heuristic)

- Primary guess: `python` (confidence: low)
- Signals:
  - Found package.json
  - Python packaging signals

## Scan results

- Code files scanned: 31
- Largest by lines: `test/test_cli_py.py` (3750 lines)

## Large files (>= 400 lines)

| File | Lines | Size |
|---|---:|---:|
| `test/test_cli_py.py` | 3750 | 149663 |
| `src/cli_commands.py` | 2497 | 93868 |
| `test/test_session_service_py.py` | 1317 | 65192 |
| `src/session_service.py` | 1190 | 46018 |
| `src/provider_runtime.py` | 769 | 29467 |
| `src/status_source.py` | 687 | 25935 |
| `test/test_runtime_py.py` | 664 | 28551 |
| `src/notify.py` | 443 | 16548 |

## Top 20 files by lines

| File | Lines | Size |
|---|---:|---:|
| `test/test_cli_py.py` | 3750 | 149663 |
| `src/cli_commands.py` | 2497 | 93868 |
| `test/test_session_service_py.py` | 1317 | 65192 |
| `src/session_service.py` | 1190 | 46018 |
| `src/provider_runtime.py` | 769 | 29467 |
| `src/status_source.py` | 687 | 25935 |
| `test/test_runtime_py.py` | 664 | 28551 |
| `src/notify.py` | 443 | 16548 |
| `src/cli.py` | 394 | 13324 |
| `src/status_view.py` | 340 | 13470 |
| `src/session_store.py` | 308 | 10667 |
| `test/test_notify_py.py` | 221 | 9028 |
| `src/update_manager.py` | 208 | 6479 |
| `src/codex_usage.py` | 197 | 6626 |
| `src/claude_usage.py` | 180 | 6443 |
| `bin/python-runner.js` | 165 | 4453 |
| `src/backup_bundle.py` | 163 | 5441 |
| `src/update_check.py` | 156 | 4944 |
| `src/cli_render.py` | 154 | 4539 |
| `src/health.py` | 137 | 4745 |

## Recommendations

- Prefer smaller files with one responsibility; split very large modules into cohesive units.
- Introduce clear folder boundaries (e.g., `src/` + subdomains) and keep entrypoints thin.
- Avoid dumping unrelated helpers into `utils/`; prefer domain-scoped helpers next to their usage.
- Keep configuration and environment wiring separate from business logic.
- Python: prefer a `src/` layout for packages when the repo grows; keep CLI/web entrypoints thin.
- Python: separate web layer (routers/views) from domain logic and persistence adapters.

## Next actions (concrete)

- Pick the top 1–3 largest files and identify natural seams (types/models, IO boundaries, feature sections).
- Extract one seam at a time into a new module/package; keep the original file as an orchestrator.
- Add a simple guardrail: fail CI if new files exceed the threshold (once the stack is known).
