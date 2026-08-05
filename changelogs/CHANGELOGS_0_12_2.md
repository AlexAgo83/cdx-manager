# CDX Manager 0.12.2

## Highlights

- `cdx ready` now exits successfully when no future reset is known, clearly reporting that no notification was scheduled.
- `cdx doctor` can filter diagnostics by severity with `--severity OK|WARN|FAIL`.
- Unknown `cdx config <name>` sessions now explain how to inspect existing sessions or create the requested one.

## Changes

### Safer ready notifications

When `cdx ready` cannot find an upcoming session reset, it returns a successful unscheduled result instead of failing. Named reset notifications with no known reset remain explicit errors.

### Filterable diagnostics

`cdx doctor --severity` accepts a comma-separated list of `OK`, `WARN`, and `FAIL` statuses. Text and JSON output retain accurate summaries for the filtered report.

### Actionable configuration errors

Unknown-session errors from `cdx config` now direct users to `cdx configs` to inspect available sessions and `cdx add <name>` to create one.

## Validation

- `npm run lint`
- `npm test`
- `logics-manager lint --require-status`
- `logics-manager audit --group-by-doc`
