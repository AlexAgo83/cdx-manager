# Unreleased

## Run costs and budgets

- Add nullable `cost_usd` to JSON history entries using the same observed usage, model pricing, and price overrides as stats.
- Add `cdx run --budget USD` to stop on measured estimated spend with exit code 125, `budget_exceeded`, and `error.spent_usd` in the final JSON. Share the budget across recovery attempts and failover; support detached runs and fresh budgets for continued runs without charging earlier turns.
- Document unknown usage/prices and delayed provider reporting, including possible budget overshoot. Cover pricing, unknown costs, validation, live process termination, Claude transcript accumulation, continuation boundaries, and detached supervision in tests.

## Remote Codex runs

- Add `cdx run --remote SSH_TARGET` with controller-owned supervision, registry, history, output, costs, budgets and detached execution.
- Refresh under the controller authentication lock at the seven-day/24-hour thresholds, then send a temporary OAuth credential over SSH stdin with an empty refresh token. Refuse rotating credentials, other providers and CLI version mismatches.
- Keep worker credentials in a private memory-backed home, clean up after success, failure and stop, and sweep dead homes on the next launch. Keep agent stdin separate from bootstrap input and report credential expiration without retrying.
- Cover transport and credential isolation, thresholds, cleanup, sweep, unreachable workers, provider refusal and registry reports with a fake SSH worker.
