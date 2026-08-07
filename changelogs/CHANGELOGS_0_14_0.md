# CDX Manager 0.14.0

> 0.13.0 was prepared but never published. Everything it contained ships here,
> so this release covers two versions' worth of work: the programmatic CLI
> surface for non-interactive callers, and the unification of session selection
> and accepted values.

## Highlights

- `cdx run --detach` launches a run without waiting and returns its `run_id` immediately; `cdx run-tail` shows a run's live output.
- `cdx schema --json` publishes the enums, constraints, and error codes callers should validate against, instead of forcing them to copy lists that drift.
- Every command that picks a session now uses one ranking, and `--priority` finally counts in all of them.
- `cdx set --permission workspace-write` works, matching what `cdx run --permission` always accepted.
- New `cdx doctor --check-provider-flags` verifies that the CLI flags cdx maps for each permission actually exist in the provider CLIs.

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

### One session selection rule

`cdx select`, `cdx run --provider`, `cdx next`, the `cdx status` recommendation, and `cdx ready` used two independent rankings that disagreed. Each knew something the other did not: the headless one filtered by provider and honored `--priority`, the recommendation one understood credits and reset scheduling. Which session you got depended on which command you asked.

They are now one function in `src/session_ranking.py`, parameterized by what each caller needs. Candidate filters (disabled, logged out, provider, effort floor, readiness) are kept separate from ordering, because describing a filter as a sort stage is part of what made the old published policy wrong.

The merged ordering is: usability class, then `--priority`, then — for a usable session — credits, availability and reset; for a session that is not usable now, reset first, since when it comes back is what matters. Reasoning effort and session name break the remaining ties.

### The priority setting counts everywhere

`cdx set <name> --priority 90` previously affected only `cdx select` and `cdx run --provider`. Status rows now carry the configured priority and effort, so `cdx next`, `cdx status`, and `cdx ready` honor it too.

Priority ranks sessions *within* a usability class, never across one: a high-priority session with no quota left does not outrank a usable one. Priority says which usable session to prefer, not where to send work that will fail there.

The `cdx status` recommendation line is now labelled `Recommended:` rather than `Priority:`. The old label named the whole recommendation after one of its inputs, so tuning `--priority` and seeing no change read as the setting being broken when availability or resets had decided instead.

### Truthful selection reporting

`cdx select --json` built its `selection_policy` from a hardcoded string that omitted the reasoning-effort tie-break and described the readiness filter as a sort stage, and a `reason` that claimed availability decided even when priority or the alphabetical fallback did.

Both are now derived. `selection_policy` is built from the ranking itself and reports factors and filters separately; `deciding_factor` and `reason` name the factor that actually separated the winner from the runner-up for that call, or report that it was the only candidate. Do not treat `selection_policy` as a stable identifier — it changes when the ranking does, which is the point.

### Selecting on fresh or missing status

`cdx run --provider` now accepts `--refresh` to fetch status before auto-selecting. Cached status remains the default, so ordinary runs do not each pay for a provider probe.

When auto-selection picks a session with no recorded availability, the run payload carries a `session_selected_without_status` warning. That is distinct from a session known to be low: on a freshly imported or long-idle set of sessions, choosing with no data at all is the ordinary case, and it was previously invisible.

### One definition of the values cdx accepts

The reasoning-effort enum was defined in four places (two of them identical, one line apart in the same module) and the permission enum in two, with `cdx set` validating against one pair and `cdx run` against another. `config.py` now owns both, and every validator, normalizer, and `cdx schema --json` derives from them. One test asserts identity rather than equality; another fails if any module restates one of these sets.

### Permission aliases work in cdx set

`cdx run --permission workspace-write` was accepted and normalized to `default`, while `cdx set <name> --permission workspace-write` failed with `Unsupported permission`. The same applied to `read-only` and `danger-full-access`, which are the provider-native spellings a user is most likely to have in hand, and `cdx schema --json` published the aliases without saying they applied to one command only.

`cdx set` and the `perm` alias command now accept them, storing the canonical value so nothing downstream has to learn aliases exist. They were added to `set` rather than removed from `run`, since removing them would break callers passing provider-native spellings today.

### Verifying provider flag mappings

cdx maps each permission to concrete provider CLI flags, and nothing verified those mappings. GitHub issue #8 was exactly that: an `--experimental-yolo` flag mapped for ollama that the ollama CLI never had, undetected until a user hit it.

`cdx doctor --check-provider-flags` checks each configured provider's installed CLI for the flags cdx maps. A rejected flag is a `FAIL` naming the provider, the permission, and the flag. An uninstalled CLI or unreadable help is a `WARN`, never an `OK` — "could not verify" is the state that bug lived in. A provider that maps nothing, such as ollama, reports `OK` with an empty mapping, so having nothing to check is distinguishable from having failed to check.

It is opt-in because it costs a provider CLI invocation per provider, and the default report carries a `provider_permission_flags_unchecked` warning rather than omitting it, so a green doctor never implies the mappings were verified.

Antigravity and ollama permission mappings also moved out of inline branches into `LAUNCH_PERMISSION_ARGS`, so every provider's mapping is declared in one table the check can read. Ollama's entry is deliberately empty.

## Internal structure

No behavior change, listed because the source layout is different if you have a patch in flight.

`cli_commands.py` (3313 lines) became nine per-domain modules under `src/commands/`, and `session_service.py` (1690 lines) became `session_service`, `session_helpers`, `session_status`, and `session_backup`. `create_session_service` went from a 1153-line factory holding 46 closures to 56 lines of assembly, with dependencies passed explicitly rather than captured.

Both original modules remain the import location for everything they exposed, so no caller changed. The split followed a coupling measurement in each case, and stopped where the measurement stopped: the session service's runtime and auth groups have no helpers of their own, so they were left in place rather than turned into files that would only re-import from elsewhere. That reasoning is recorded in `session_service`'s docstring, with a test that fails if someone finishes the job by instinct.

## Behavior changes

- **`--priority` now outranks availability.** It previously sat below availability in the headless sort, so it only broke exact ties and was effectively inert. A session with lower availability but higher priority now wins within the same usability class. This is the change that makes the setting mean anything.
- **Ties on session name now sort ascending everywhere.** The recommendation ranking sorted names descending as a side effect of reversing its whole sort tuple, disagreeing with the headless ranking. The ascending order is kept.
- **Logged-out sessions are never selection candidates.** `cdx select` without `--require-ready` could previously return one. `--require-ready` remains stricter still: it requires a confirmed `authenticated` state, so a session whose auth has never been checked is not offered to `cdx run --provider`.
- `cdx status`'s recommendation line is labelled `Recommended:` instead of `Priority:`.
- `cdx select --json`'s `selection_policy` is now a structured object rather than an underscore-joined string.

## Fixes

- `cdx --version` reported a stale release. `src/cli.py` restated the version as a fourth hardcoded copy alongside `VERSION`, `package.json`, and `pyproject.toml`, and nothing kept the four in step — it had been left at 0.12.4. The version is now resolved from the `VERSION` file in a checkout and from installed package metadata otherwise, and a test fails if any of the four (plus the README badge) disagree.
- The release validator was left scraping a `VERSION = "..."` literal out of `src/cli.py`, which the fix above had removed. It resolved an empty string and rejected every release with "Missing release version in: src/cli.py" — inside the publish workflow, after the tag was already public. It now reads the resolved version, and a test fails if any declaration site stops yielding one.
- Two tests still asserted the `--experimental-yolo` flag removed from ollama launches in 0.12.4 (GitHub issue #8); the launch behavior was already correct, the stale expectations are now aligned.
- `format_json_error` honors an error's declared code instead of always re-deriving one from the message prefix, so structured argument errors keep their code when they reach the CLI entry point.
- The detached-run test asserted the POSIX `start_new_session` unconditionally, so the Windows CI job failed on a code path that was correct. The assertion is now platform-aware, and Windows CI exercises the `creationflags` branch for the first time.

## Review fixes

Found by a review pass over the programmatic CLI work, before release:

- The detached child's `CDX_RUN_ID` is consumed rather than read, so it is no longer inherited by the provider process. Left set, an agent making its own nested `cdx run` would have claimed the outer run's id, deleting its registry record and truncating its stdout, stderr, and transcript files.
- The detached child receives the resolved absolute `--cwd`; a relative path would have resolved against the child's own working directory.
- `--detach` now detaches correctly on Windows (`DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`), and always re-invokes through `sys.executable -m` rather than `sys.argv[0]`, which is not reliably executable there.
- `network_disabled_by_permission` now fires when no `--permission` is given at all — the most common invocation, where `codex exec` still applies its own sandboxed default. It previously exempted exactly the case it was written for.
- `cdx run-tail` on a run that has not written its first byte returns `lines: []` instead of failing, so the launch-then-tail flow does not report a fatal error during that window. A missing output file on a *finished* run is still an error.
- `run-tail` drops a partial leading line when the read window opens mid-line, rather than returning a fragment as if it were a whole line.
- `cdx schema --json` publishes every error code the run commands emit, grouped by area, plus the warning codes; and `--reasoning-effort`/`--power` moved from `mutually_exclusive` to a new `must_match` group, since cdx accepts both when they agree.
- An empty `--power ""` blames `--power` instead of `--reasoning-effort`.
- `format_json_error` emits the same error field set as the run payload, so callers do not need two shapes.
- The prompt a detached launch stages for its child is deleted once the child reads it, instead of leaving a permanent cleartext copy in the session log directory.

## Validation

- `npm run lint`
- `npm test` — 565 tests.
- CI green on ubuntu-latest and windows-latest.
- End-to-end: detached launch returning `run_id`, `run-tail` against the in-flight run after the launcher exited, terminal status reached without a supervisor, and `runs --since` reporting the completion.
- End-to-end: with one session at 80% availability and priority 0 and another at 40% and priority 90, `cdx select`, `cdx next`, and `cdx status` all name the second, and `cdx select` reports `decided on priority`.
- The issue #8 condition reproduced against the new provider flag check: mapping `--experimental-yolo` for codex fails the check by name. All four provider CLIs verified against their real binaries.
- `logics-manager lint --require-status`
- `logics-manager audit --group-by-doc` — 0 blocking, 0 warnings.
