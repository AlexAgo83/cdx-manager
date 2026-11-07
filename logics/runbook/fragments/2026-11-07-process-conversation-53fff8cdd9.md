# Safe process conversation boundary (mission 53fff8cdd9)

## Existing capability and consumer failure

remote-ops on Tower runs `cdx work2` in an interactive terminal. Fresh Codex
launches have no resume argument. Workspace/recency lookup returned an unrelated
older transcript during a live exchange. Existing explicit-ID lookup and
pagination are reusable once a native ID is known, but no existing process-scoped
selector or native selected-thread association was found.

## Delivered API and conservative result

`cdx conversation work2 --pid N --tail 20 --json` and the Python
`read_conversation(..., pid=N)` API now expose process resolution status, method,
conversation ID and an opaque Linux process lifetime guard. Retain that guard and
pass `--process-identity` on subsequent calls to reject PID reuse. Supply the
native Codex child PID, not the tmux pane shell or CDX supervisor.

The current result is explicitly unknown with no conversation ID or entries.
Kernel process identity is verifiable, but no verified provider event associates
that process with its currently selected thread/profile. An open rollout is not
sufficient: it may belong to a retained thread while a newly selected thread has
not created its rollout. This alternative was rejected during review instead of
being shipped as a fabricated match. Resume argv, cwd, profile and recency are
never used as substitutes. Process mode rejects unbound cursors without replaying
entries. Explicit-ID and existing pagination behavior stay unchanged.

## Measured boundary

A timed isolated PTY probe ran installed `codex-cli 0.167.0` with a new provider
home, a fake model provider at an unavailable loopback endpoint and an initial
fake prompt. After eight seconds the process remained alive but exposed no usable
open rollout evidence. The probe returned unknown and no ID/entries. This does
not measure an authenticated exchange, resumed launch or conversation switch on
Tower. Controlled kernel writer tests verify distinct process identities and safe
absence; they are not proof of native selected-conversation attribution.

Focused regressions cover fresh/resumed process evidence, concurrent same-profile
writers, sole retained writers, switches, ambiguity, wrong profile/user/process,
dead/reused PIDs, unavailable/oversized evidence, unsupported platforms, cursor
isolation and unchanged explicit-ID pagination. The API lets remote-ops consume an
honest unknown without parsing native formats; positive live native resolution
remains unavailable.

## Smallest tracking extension and supervision

A provider-native lifecycle event must carry the selected native conversation ID
on fresh start, resume and every switch. Bind it atomically to the child boot
ID/PID/start ticks, profile and monotonic selection generation; invalidate on exit.
Then resolve only that record and bind cursors to the same generation. An original
resume argument, sole open/new file or launch timestamp cannot implement this.
A verified source of these lifecycle events is still required; no provider launch
flags, dependencies or host installations are changed by this mission.

For the real host measurement, the supervisor sets `CODEX_PID` to the native child
in `jarvis-remote-ops`. As `aagos` on Tower, run this exact read-only probe after a
fresh launch, resume and switch, including concurrent same-profile/cwd sessions:

```bash
cdx conversation work2 --pid "$CODEX_PID" --tail 1 --json
```

The current acceptance result is unknown with null ID and no entries. Positive
attribution must not be claimed until a native event source exists and its returned
ID is compared with the TUI's selected ID. Retain/resend process identity to test
exit and PID reuse. No access to Tower or its authenticated TUI is available here.

Jarvis owns commits, PR review, trusted secret scanning and automatic merge after
required green CI on the merged commit. Supervising delivery must publish/install
the resulting CDX version on Tower for remote-ops to use the explicit boundary;
this isolated mission does not release or install CDX on a host.

## Final local validation

- `env -u GIT_DIR -u GIT_COMMON_DIR -u GIT_WORK_TREE -u RTK_DB_PATH uv run npm test`: 1,936 passed, 5 skipped.
- `uv run npm run lint`: passed, including compilation and project documentation checks.
- `cargo test --manifest-path tray/Cargo.toml` with a temporary workspace-local Rust toolchain on PATH: 99 passed.
- `npm pack --dry-run` and `uv build --wheel --out-dir .jarvis-artifacts/wheels`: passed.
- Timed final native PTY probe: live Codex 0.167.0 returned `unknown`, `native_conversation_identity_unavailable`, null ID.
- Logics lint passed; audit reported no blocking issues and six existing warnings outside this fragment.

All attempts, including earlier dependency/environment failures and an execution
that overlapped the conservative implementation revision, remain in the supplied
timer receipts. Final checks supersede those attempts. GitHub CI, trusted secret
scanning and independent PR review are publication obligations for Jarvis.
