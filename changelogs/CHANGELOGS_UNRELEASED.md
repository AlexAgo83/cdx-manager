# Unreleased

## Run costs and budgets

- Add nullable `cost_usd` to JSON history entries using the same observed usage, model pricing, and price overrides as stats.
- Add `cdx run --budget USD` to stop on measured estimated spend with exit code 125, `budget_exceeded`, and `error.spent_usd` in the final JSON. Share the budget across recovery attempts and failover; support detached runs and fresh budgets for continued runs without charging earlier turns.
- Document unknown usage/prices and delayed provider reporting, including possible budget overshoot. Cover pricing, unknown costs, validation, live process termination, Claude transcript accumulation, continuation boundaries, and detached supervision in tests.
