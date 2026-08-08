# CDX Manager 0.15.1

> Two fixes, both for failures that only appear under the conditions cdx is
> built for: an account whose credits ran out while its usage windows still
> read healthy, and twenty parallel runs writing the registry at once on
> Windows.

## Fixes

### Failover missed an exhausted account when its windows looked fine

`--failover` corroborates a rate-limited run against the account's own
refreshed status before migrating, so a healthy account is never abandoned on
the strength of a matched phrase. That check read only the 5-hour and weekly
percentages, which cannot see credit exhaustion: an account with 88% of its
5-hour window and 70% of its weekly window remaining, and no credits, was
reported as not spent. The run failed instead of moving, on an account that
could not have succeeded.

Codex publishes a typed reason for this — `rate_limit_reached_type`, null in
normal operation and set to a value such as `workspace_owner_credits_depleted`
when a limit is actually reached. cdx was already fetching that payload and
dropping the field; it survived only inside `raw_status_text`, unparsed. It is
now surfaced and treated as authoritative.

Any non-null value counts. The enum belongs to the provider, and carrying a
list of its members in cdx would reintroduce exactly the drift this removes —
a value nobody has seen yet would silently mean "not exhausted".

### Concurrent registry writes failed on Windows

`_registry_lock` used `msvcrt.locking(LK_LOCK)`, which does its own waiting —
ten attempts, one second apart — and then raises `EDEADLOCK`. POSIX
`fcntl.flock` blocks until the lock frees. Identical contention therefore
produced a wait on one supported platform and an `OSError` on the other.

Twenty parallel runs writing the run registry is not an edge case for this
tool; it is the load it exists to carry. Windows now takes the non-blocking
form and waits in a loop cdx controls, bounded by a deadline cdx chooses rather
than by `LK_LOCK`'s fixed budget. An exhausted wait raises a named error
instead of a raw `OSError`, so contention is distinguishable from a bug.

This predates 0.15.0 — it reproduces on the `v0.14.0` tag — and CI never showed
it, a hosted runner being less contended than a physical desktop. Which also
means CI could not be the evidence for the fix.

## Also in this release

- A test now fails if a flag is declared in a parser's schema and never used,
  which is how `--failover` shipped in 0.15.0 parsing, validating and doing
  nothing until an integration test caught it by chance.
- `scripts/measure_option_sites.py` records the measurement behind that
  decision: of the nine declaration sites an option touches, six restate one
  fact and three encode a real decision, so the answer was a check rather than
  a consolidation.

## Validation

- `npm run lint`
- `npm test` — 639 tests.
- CI green on ubuntu-latest and windows-latest.
- On a physical Windows machine: 632 passed, 5 skipped, **no failures** —
  including `test_concurrent_starts_do_not_lose_records`, which had failed
  there on every run since before v0.14.0.
- The credit-exhaustion case verified against the real payload shape recovered
  from local transcripts: with 88% and 70% of the windows remaining and a typed
  reason present, corroboration now confirms where it previously did not.

## What closed from 0.15.0's known gaps

- **Claude's rate-limit wording** was unobserved and now is not. Recovered from
  local session transcripts: `type: rate_limit_error` under HTTP 429, already
  covered by the existing matcher. Worth knowing, and now pinned by tests: the
  same 429 is how an org policy disabling a model is reported, a case no
  failover can fix, and the status corroboration is what keeps a healthy
  account from being abandoned for it.

## Still open

- The rate-limit wording of a personal-plan Codex account remains unobserved.
  The `account_status_exhausted` route covers it, so this costs the precise
  reason rather than the failover itself.
- Background delegation is still opt-in behind `CDX_EXPERIMENTAL_NATIVE_BG=1`.
  It works and is verified end to end, but on one account with one prompt
  shape — an exposure judgement, not a correctness one.
