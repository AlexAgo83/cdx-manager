# Unreleased

## Dependency security

- Require cryptography >=50.0.0 for encrypted auth bundles and remove the vulnerable 47.0.0 lock entry. Python 3.9 remains supported from 3.9.2, as cryptography 50 excludes 3.9.0 and 3.9.1.
- Require pytest >=9.0.3 in the development extra on Python >=3.10; retain the existing 9.2.0 lock entry. pytest is not a runtime dependency. Python 3.9 still uses 8.4.2, the last compatible release, and its medium-severity alert remains unresolved pending an upstream backport or a decision to drop Python 3.9 development support.
- Check lock consistency and run the CI test matrix against locked development dependencies without upgrading unrelated packages.

## Run costs and budgets

- Add nullable `cost_usd` to JSON history entries using the same observed usage, model pricing, and price overrides as stats.
- Add `cdx run --budget USD` to stop on measured estimated spend with exit code 125, `budget_exceeded`, and `error.spent_usd` in the final JSON. Share the budget across recovery attempts and failover; support detached runs and fresh budgets for continued runs without charging earlier turns.
- Document unknown usage/prices and delayed provider reporting, including possible budget overshoot. Cover pricing, unknown costs, validation, live process termination, Claude transcript accumulation, continuation boundaries, and detached supervision in tests.

## Remote Codex runs

- Add `cdx run --remote SSH_TARGET` with controller-owned supervision, registry, history, output, costs, budgets and detached execution.
- Refresh under the controller authentication lock at the seven-day/24-hour thresholds, then send a temporary OAuth credential over SSH stdin with an empty refresh token. Refuse rotating credentials, other providers and CLI version mismatches.
- Keep worker credentials in a private memory-backed home, clean up after success, failure and stop, and sweep dead homes on the next launch. Keep agent stdin separate from bootstrap input and report credential expiration without retrying.
- Cover transport and credential isolation, thresholds, cleanup, sweep, unreachable workers, provider refusal and registry reports with a fake SSH worker.

## Remote worker transport and isolation preflight

- Add `--remote-prefix` for Windows SSH landings such as `wsl.exe -d Ubuntu --`, including detached runs. Keep the POSIX default and use a short double-quoted bootstrap on argv; send framed worker/sandbox source and then credentials/payload over stdin.
- Probe the local bubblewrap/pasta/nftables isolation mechanism on the worker with dummy credentials, including namespace/network startup. Refuse missing dependencies or setup failures without falling back to an unisolated run.
- Enable remote isolated Codex execution after a successful isolation probe, following the operator decision of 2026-11-01. Agent tools can read the copied access token (up to ten days of validity); missing dependencies still refuse without fallback.
- Release the controller authentication lock after preparing the credential snapshot so scheduled authentication refresh can run during long remote missions. Keep profile mission exclusion in the run registry and the worker credential's original expiry.
- Test cmd.exe length/quoting enforcement, Windows prefixes, large stdin payloads, POSIX transport, sanitized credential snapshots, sandbox construction/dependencies and concurrent scheduled refresh with synthetic credentials.

## Isolated Codex credentials

- Replace the local full-profile auth mount with a mode-600 run-private snapshot on verified memory-backed storage, containing an empty refresh token. Refresh on the controller under the auth lock at the existing seven-day/24-hour thresholds before launch.
- Keep snapshots independent of controller refresh during long missions, prohibit authentication writeback, enforce their original expiry, and remove temporary storage after success, failure and stop. Non-isolated local authentication remains unchanged.
- Reject rotating credentials at the sandbox boundary. Test snapshot contents, permissions, cleanup, refresh lock ownership, concurrent controller refresh, remote isolation through fake SSH and missing dependency refusal.
- The separately maintained remote-ops `scripts/workspace_sandbox.py` requires the same credential guard and run-private lifecycle integration; it is not shipped by this repository.
