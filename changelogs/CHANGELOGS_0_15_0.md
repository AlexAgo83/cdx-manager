# CDX Manager 0.15.0

> Quota awareness stops being advice. A headless run that hits a rate limit now
> continues on an account that still has quota, and `cdx resume` reopens the
> conversation cdx named rather than whatever ran here last.

## Read this first

Two defaults change for existing sessions.

- **`cdx resume <name>` changes meaning.** It used to run `codex resume --last`
  or `claude --continue`, both of which mean "the most recent conversation in
  this directory". It now names the provider's own conversation id, so it
  reopens the conversation *that session* last had, regardless of your working
  directory or of what ran since. Sessions with no recorded id keep the old
  behaviour; `cdx can-resume --json` tells you which applies.
- **Every Claude launch now carries `--session-id`.** cdx mints the id and
  passes it, which is what makes the above possible.

## Highlights

- `cdx run --failover` continues a task on the next eligible account when the
  one it started on runs out, keeping one `run_id` for the whole task.
- `cdx set --budget` caps what a headless run may spend; `--fallback-model`
  lets it continue on another model when the first is unavailable.
- `cdx set --extra-args` passes provider flags cdx does not model straight
  through, so a flag your provider shipped last week no longer forces you out
  of cdx.
- Resume and handoff are anchored on a provider-native conversation id instead
  of on recency.
- Opt-in delegation of `cdx run --detach` to Claude Code's own background
  agents, behind `CDX_EXPERIMENTAL_NATIVE_BG=1`.

## Changes

### Failover across accounts

`cdx run --failover` detects that a run stopped because its account is spent,
re-ranks the remaining sessions through the same ranking `cdx next` uses,
carries the task across, and continues. The whole task keeps one `run_id`;
`cdx run-report` lists every session it occupied, in order, with the reason for
each transition, and `cdx runs` shows it once.

Migration requires the account's own refreshed rate-limit status to confirm it
is spent, because the two ways of being wrong are not symmetric: missing a rate
limit costs nothing new, while inventing one would move a healthy run off a
working account and spend a second account's quota redoing it.

Two routes trigger it. `provider_reported_exhaustion` when the provider says so
in words cdx recognises, and `account_status_exhausted` when the quota is gone
and the run failed, whatever the wording. The second exists because the wording
is not one thing — an enterprise workspace out of credits, a personal plan
hitting its 5-hour window, and Claude's own phrasing are different sentences,
and only the first has been observed.

Exhausting every eligible account reports `failover_exhausted`, and hitting the
transition bound reports `failover_limit_reached`; both are distinct from the
task itself failing. `--failover` and `--detach` are mutually exclusive:
failover has to watch the run to react.

### Spend ceiling and model fallback

`cdx set <name> --budget 5` and `--fallback-model sonnet,haiku` persist like
every other launch setting. Both are Claude Code flags the provider accepts
only alongside `--print`, so they apply to `cdx run` and to nothing else;
`cdx configs` says so rather than letting a launch fail. `--fallback-model`
takes a comma-separated list, tried in order.

### Resume by identity

Sessions record the provider's own conversation id and where it came from.
Claude accepts a caller-supplied id, so cdx mints it at launch — provenance
`imposed`. Codex mints its own, so cdx reads it back from the rollout after a
run — provenance `observed`, and legitimately absent until the session has run
once. `cdx can-resume --json` reports the strategy, the id, and its provenance,
so an automated caller can tell a named resume from a best-effort one.

### Passthrough for unmapped provider flags

`cdx set <name> --extra-args "--add-dir ../shared"` reaches the provider
command line unmodified, after the arguments cdx maps itself, so a passthrough
value overrides the setting it duplicates. These arguments are explicitly
unvalidated: `cdx schema --json` lists them under `unvalidated` rather than
describing them, and `cdx doctor --check-provider-flags` ignores them. They are
split into literal argv entries and never passed through a shell.

### Background delegation (opt-in)

With `CDX_EXPERIMENTAL_NATIVE_BG=1`, `cdx run --detach` hands the run to Claude
Code's background agents. The run keeps its cdx `run_id`, closes out with the
token usage and final answer read from the provider's own session transcript,
and the parked session is stopped once its task is done. Off by default for
this release: it works, but it has been exercised far less than the in-house
launcher every run takes today. Codex keeps the in-house path while its
`cloud` and `exec-server` surfaces are marked experimental.

### Onboarding and docs

`cdx` with no sessions registered now points at `cdx add` instead of listing
ten commands that all return nothing. The README leads with the quota routing
rather than with session management, and its screenshots are generated from a
synthetic home (`scripts/seed_demo_home.py`) so they carry no account names.

### Fixes

- A status merge adopted the candidate's timestamp even when it was older,
  dating a record by its stalest contributor. Since `updated_at` drives the
  freshness check, a just-resolved status read as expired and re-probed the
  provider on every call.

## Validation

- `npm run lint`
- `npm test` — 629 tests.
- CI green on ubuntu-latest and windows-latest.
- Also run on a physical Windows machine: 623 passed, 5 skipped. One failure,
  `test_concurrent_starts_do_not_lose_records`, reproduces identically on the
  `v0.14.0` tag on that machine and passes in CI — a pre-existing contention
  flake in the registry lock, not a regression.
- End-to-end across eleven live sessions and both providers: fourteen real
  runs, usage extracted on every one, six Codex accounts each recording a
  distinct conversation id and five Claude accounts recording theirs.
- End-to-end failover on a genuinely exhausted account: `work6` migrated to
  `work1` and the task succeeded, recorded as one run.
- End-to-end resume by identity: a minted id accepted as `--session-id`, then
  `--resume` on that id recalling the previous turn's answer.
- `--extra-args` and the budget/fallback settings exercised against real
  provider CLIs, not only in tests.
- `logics-manager lint --require-status`
- `logics-manager audit --group-by-doc` — 0 blocking, 0 warnings.

## Known gaps

- The rate-limit wording of a personal-plan Codex account has not been
  observed; only an enterprise workspace out of credits has. Claude's wording
  was recovered from local transcripts after the release was cut - it reports
  `type: rate_limit_error` under HTTP 429, which the matcher already covers.
  Worth knowing: that same 429 is also how an org policy disabling a model is
  reported, a case no failover can fix, and the status corroboration is what
  stops a healthy account being abandoned for it. The
  `account_status_exhausted` route covers whatever wording remains unseen, so
  this costs the precise reason rather than the failover itself.
- Background delegation has been exercised on one account with one prompt
  shape, which is why it is opt-in.
