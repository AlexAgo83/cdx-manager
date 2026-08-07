# CDX Manager 0.13.0

## Highlights

- `cdx run --detach` launches a run without waiting and returns its `run_id` immediately.
- New `cdx run-tail` shows a run's live output; new `cdx schema --json` publishes the enums and constraints callers should validate against.
- Argument failures now report a specific `error.code` and name the offending arguments instead of one catch-all `invalid_request`.

## Changes

### Detached runs

`cdx run --detach --json` registers the run, starts the provider detached from the invoking process, and returns straight away with `detached: true`, the assigned `run_id`, `pid`, and the artifact paths. The child is placed in its own session so it outlives the launcher, including when cdx was invoked over an SSH command that returns immediately, and it transitions its own registry entry to a terminal status so `cdx runs` and `cdx run-status` stay accurate with nobody supervising. Authentication is still resolved before the launch returns, so a login problem surfaces synchronously rather than in the background.

Callers no longer have to poll `cdx runs` and guess which row belongs to the run they just started.

### Live run output

`cdx run-tail <run_id> [--lines N] --json` returns the last lines of a run's recorded `stdout_path` plus its current status, while the run is still going or after it finished. Undecodable provider bytes are returned with replacement characters rather than failing the call. A run with no recorded output path reports `run_output_unavailable`, distinct from an unreadable one.

### Specific argument error codes

Argument and usage failures previously collapsed into `invalid_request` carrying the full human usage line, so a missing `--cwd` was indistinguishable from passing a session name and `--provider` together. They now report `missing_required_argument`, `mutually_exclusive_arguments`, `invalid_argument_value`, `argument_value_out_of_range`, or `unknown_argument`, and the error object gained `arguments` and `allowed_values` fields naming the offending arguments as data. The human-readable message and the exit codes are unchanged.

`invalid_reasoning_effort` is kept for an unsupported `--reasoning-effort`/`--power` value; supplying two conflicting values now reports `mutually_exclusive_arguments`, since the two flags are aliases of one setting.

### Schema discovery

`cdx schema --json` publishes the accepted values for `permission` (with aliases and canonical forms), `reasoning_effort`/`power`, `kind`, and `provider`, the declared mutually-exclusive argument groups, and the argument error codes. Values are read from the same definitions the parser validates against, and a test fails if the two disagree, so downstream callers can stop maintaining copies that drift.

### Prompts on standard input

`cdx run --prompt-file -` reads the prompt from standard input, so a caller relaying arbitrary text no longer has to stage and clean up a temporary file or place the text on a command line. It fails immediately with `invalid_argument_value` if standard input is a terminal.

### Completion cursor for runs

`cdx runs --since <cursor> --json` returns every run that completed after the cursor, accepting the same cursor forms as `cdx history --since`. The cursor bounds the result by time rather than row count: `--limit` is ignored when `--since` is given, and the payload says so in `warnings`. Capping a cursor query by row count would silently drop completions a polling caller had not yet seen. Runs still in flight are excluded until they complete.

### Run warnings

The run payload's `warnings` list was declared in the contract but hardcoded empty. It is now populated, on the successful path as much as the failing one. The first warning, `network_disabled_by_permission`, fires when a Codex-backed run uses a permission below `full`: Codex ties network access to its sandbox, so the run cannot resolve DNS and network-dependent tooling fails inside a run that still exits zero. The condition is read from the same permission-to-flag mapping the launch spec uses, so adding a permission cannot leave it behind.

## Fixes

- Two tests still asserted the `--experimental-yolo` flag removed from ollama launches in 0.12.4 (GitHub issue #8); the launch behavior was already correct, the stale expectations are now aligned.
- `format_json_error` honors an error's declared code instead of always re-deriving one from the message prefix, so structured argument errors keep their code when they reach the CLI entry point.

## Validation

- `npm run lint`
- `npm test`
- End-to-end: detached launch returning `run_id`, `run-tail` against the in-flight run after the launcher exited, terminal status reached without a supervisor, and `runs --since` reporting the completion.
- `logics-manager lint --require-status`
- `logics-manager audit --group-by-doc`
