# Antigravity integration on current main — mission 6cceecb079

## Scope and decision

Apply local commit `9b8a84b` from `origin/jarvis/mission-44674fc58c` to
current main without modifying Git history. Preserve its changelog entry,
worker implementation, operator probe and original evidence fragment.

Keep the existing main headless launch branch, including profile HOME through
`_antigravity_env_overrides`, launch configuration and extra arguments. Add the
incoming branch's model argument to that branch. Do not introduce a second
Antigravity branch or worker authentication into the local supervisor.

Mandatory isolation and worker-owned authentication apply only to remote runs.
`remote_worker.main` already owns `antigravity_attempt`; the local supervisor
needs no duplicate worker credential path. Local CLI runs retain their profile
HOME, authentication check and token. The regression test runs a local profile
named `gemi` while explicitly rejecting any worker token or sandbox access.
This is a compatibility fix whose reasoning is recorded by the failing
regression tests at the affected boundary (ADR 030); no new workflow chain is
needed.

Preserve main's explicit Antigravity `total_tokens` behavior. The remote fake
provider now reports `total_tokens: 16`. Additional tests prove that an absent
total stays unknown and a reported total is retained even when it differs from
the sum of the other counters. No derived total is introduced.

## Preserved remote guarantees

- Memory-backed attempt HOME, removed on completion or timeout.
- `ANTIGRAVITY_TOKEN_PATH` remains the constant name; fake token values contain
  `fake`. The worker token is bound read-only, never copied into attempt storage
  or transported to the controller.
- Owner, mode and symlink checks, exclusive nonblocking token lock, automatic
  CLI updates disabled, closed stdin and output redaction before SSH forwarding.
- Google destination allowlist and private-range denial, even when broader tool
  networking is requested.
- Explicit errors for missing or unsafe login, session expiry, refused actions,
  concurrent attempts and missing or unsuccessful completion status.

## Verification environment

Every local validation attempt uses `.jarvis-input/mission-test-runner.py`.
The unmodified receipts are in `.jarvis-artifacts/mission-tests.jsonl`.
Initial system-Python lint lacked Ruff; `uv sync --frozen --extra dev` supplies
it through `uv run --no-sync`. A temporary minimal public Rust toolchain under
`/tmp/mission-6cceecb079-cargo` and `/tmp/mission-6cceecb079-rustup` supplies Cargo.
No operator credentials were accessed.

The initial suite inherited `RTK_DB_PATH`, causing two unrelated RTK assertions.
It also inherited `GIT_DIR`, `GIT_COMMON_DIR` and `GIT_WORK_TREE`, causing four
Git fixture failures before the changed behavior ran. Those variables redirect
temporary repositories to the shared checkout. Run the complete suite with all
four variables removed from its environment; repository files, Git permissions
and the fixture code remain unchanged. Earlier failures remain in timer receipts.

## Human measurement still outstanding

The original fragment's live worker acceptance and refresh observations remain
pending. Fixtures establish code behavior only. This sandbox lacks strace and
an authorized operator session; no login, credential search or live inference
was attempted. On Spire as service user `aagos`, from this checkout, use the
existing read-only agent-task probes:

```bash
uv run --no-sync python -m scripts.probe_antigravity_worker
uv run --no-sync python -m scripts.probe_antigravity_worker --isolated
```

Require native and isolated JSON SUCCESS with numeric reported usage; verify
that observed HTTPS peers match the minimum candidate destinations and record
an actual refresh's inode, metadata and 0600-mode observations. An unchanged
token on an ordinary request does not establish refresh behavior. Keep the token
mount read-only until real evidence warrants a policy change. These probes may
update native session metadata but forbid tools, commands and file access by
the provider; they expose only sanitized measurements.

## Final measured validation

| Exact command | Result | Seconds |
| --- | --- | --- |
| `uv run --no-sync npm run lint` | Passed | 0.492 |
| `env -u RTK_DB_PATH uv run --no-sync python -m pytest test/test_remote_antigravity_py.py test/test_antigravity_usage_py.py -q` | 39 passed | 6.064 |
| `env -u RTK_DB_PATH -u GIT_DIR -u GIT_WORK_TREE -u GIT_COMMON_DIR uv run --no-sync npm test` | 1487 passed, 4 skipped | 97.689 |
| `env CARGO_HOME=/tmp/mission-6cceecb079-cargo RUSTUP_HOME=/tmp/mission-6cceecb079-rustup /tmp/mission-6cceecb079-cargo/bin/cargo test --locked --manifest-path tray/Cargo.toml` | 99 passed | 9.912 |
| `uv build` | sdist and wheel built | 0.925 |
| `npm pack --dry-run` | Passed | 0.344 |
| `logics-manager lint --require-status` | Passed | 0.264 |
| `logics-manager audit --group-by-doc` | Passed; six existing warnings | 0.387 |
| `uv run --no-sync python -m scripts.probe_antigravity_worker --help` | Passed; no provider started | 0.073 |

The complete final suite log is `.jarvis-artifacts/full-suite-isolated-env.log`.
The four skipped cases are the existing real bubblewrap Git/RTK boundary tests
(local and shipped-worker implementations, writable and read-only workspaces);
this sandbox cannot create the required namespaces. No tests were excluded from
the full-suite command. No dedicated typecheck script exists. No UI changed.
All code tests pass after isolating the inherited environment. Nothing was
committed, pushed or published by this mission.
