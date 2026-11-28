## item_171_prove_the_remote_messaging_loop_on_linux_macos_and_windows - Prove the remote messaging loop on Linux, macOS and Windows
> From version: 0.26.14
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 75%
> Complexity: Medium
> Theme: remote-session-control
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-11-28 09:59:47
> Owner: Codex

# AI Context
- Summary: Keep platform automation reproducible while tracking authenticated live checks separately.
- Keywords: prove, remote, messaging, loop, linux, macos, windows
- Use when: validating remote-control delivery or recording platform evidence.
- Skip when: changing provider protocols without changing their validation.

# Problem
- Process control, sockets and terminals differ per platform; a Linux-only proof would not hold.

# Scope
- In:
  - Fake-provider tests for the switch loop, queue, interrupt, endpoint access and event mapping, run in CI on the three platforms.
  - A documented live check script against the real Claude and Codex CLIs, run once per platform before release.
- Out:
  - Live provider calls in CI.

# Acceptance criteria
- AC6: Existing suites stay green with the feature disabled.
- AC7: The new tests pass on the three platforms and the live check is recorded for each.

# AC Traceability
- request-AC6 -> This backlog slice. Proof: AC6: Existing suites stay green with the feature disabled.
- request-AC7 -> This backlog slice. Proof: AC7: The new tests pass on the three platforms and the live check is recorded for each.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_058_remote_control_of_interactive_sessions_through_provider_protocols`
- Architecture decision(s): (none yet)
- Request: `req_083_protocol_based_remote_messaging_for_interactive_sessions`
- Primary task(s): `task_088_implement_protocol_based_remote_messaging_for_interactive_sessions`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.

# Executions
| When | Runner | Run id | Title | State | PR | Notes |
| --- | --- | --- | --- | --- | --- | --- |

# Validation evidence and remaining checks

Recovery wave, 2026-11-28: this item remains In progress at 75%; task_088 is
In progress at 90% and req_083 is In progress. These are delivery estimates,
not acceptance percentages. No closeout is requested.

- CI configuration retains Ubuntu, macOS and Windows, adds a 20 minute bound
  and always uploads per-platform JUnit reports. Passing GitHub runs for this
  change are pending publication by Jarvis; none are claimed here.
- Linux targeted tests initially passed: 36 passed, one intentional Antigravity
  skip. After adding the current Claude channel interrupt test, the remote suite
  plus the Git-dependent regression tests passed: 61 passed, one skipped
  (12.419 seconds including runner overhead).
- Linux CLI preflight: Claude Code 2.1.332 and codex-cli 0.172.0 are installed.
  Suppressed-output auth status returned 1 for Claude and 0 for Codex.
  A subsequent real Codex app-server probe passed initialization, thread creation,
  turn delivery, assistant response and completion in 4.031 seconds. It used the
  existing provider authentication without inspecting credentials or printing
  provider output. This proves the real Codex protocol only, not TUI sharing,
  interruption or the full cdx messaging loop. No login was attempted.
  Current Linux end-to-end live delivery remains open.
- Required GitHub CI must be green on the merged commit before merge.
- Full manual procedure, setup, exact message commands, expected events and
  cleanup: [remote control validation](../../docs/remote-control-validation.md).

Keep these checks open until sanitized authenticated evidence is recorded:

- [ ] Linux: launch `node bin/cdx.js remote-claude` and
  `node bin/cdx.js remote-codex`; run every Linux/macOS command block in the
  validation guide, including interruption and recovery. Claude needs login.
- [ ] macOS Claude channel: `node bin/cdx.js remote-claude`,
  `node bin/cdx.js send remote-claude --status --json`,
  `printf '%s\n' 'Remember the marker REMOTE_FAKE_CHECK and reply READY.' | node bin/cdx.js send remote-claude --stdin`,
  `node bin/cdx.js send remote-claude --interrupt`; complete the context,
  long-turn, recovery and cleanup commands in the Linux/macOS blocks.
- [ ] macOS Codex: `node bin/cdx.js remote-codex`,
  `node bin/cdx.js send remote-codex --status --json`,
  `printf '%s\n' 'Remember the marker REMOTE_FAKE_CHECK and reply READY.' | node bin/cdx.js send remote-codex --stdin`,
  `node bin/cdx.js send remote-codex --interrupt`; complete the same guide.
- [ ] Windows Claude channel: `node bin/cdx.js remote-claude`,
  `node bin/cdx.js send remote-claude --status --json`,
  `'Remember the marker REMOTE_FAKE_CHECK and reply READY.' | node bin/cdx.js send remote-claude --stdin`,
  `node bin/cdx.js send remote-claude --interrupt`; complete the PowerShell
  context and recovery commands. Native Windows lacks the tmux interrupt path;
  leave interruption unproven unless demonstrated in a supported terminal.
- [ ] Windows Codex: `node bin/cdx.js remote-codex`,
  `node bin/cdx.js send remote-codex --status --json`,
  `'Remember the marker REMOTE_FAKE_CHECK and reply READY.' | node bin/cdx.js send remote-codex --stdin`,
  `node bin/cdx.js send remote-codex --interrupt`; complete the PowerShell guide.
- [ ] Attach green Ubuntu, macOS and Windows CI job URLs for the published change.

The global Logics audit has three pre-existing blockers outside this slice:
prod_059 lacks its overview Mermaid diagram; req_084 has no linked backlog and
is Done without linked delivery evidence. Leave those unchanged and mention them
in the PR. They are not a gate for publishing this partial validation work.

## Final local command receipts

All attempts used the supplied mission timer. Durations below come from its
receipt, including runner overhead. The virtual environment scripts directory
was on PATH after `uv sync --frozen --extra dev`.

| Exact command | Result | Duration (s) |
| --- | --- | --- |
| `env -u GIT_DIR -u GIT_WORK_TREE -u GIT_COMMON_DIR npm test` | 2154 passed, 6 skipped | 76.420 |
| `python -m pytest test/test_remote_control_py.py --junitxml=.jarvis-artifacts/remote-control.xml` | 37 passed, 1 skipped | 11.970 |
| `npm run lint` | Passed, including Python compilation | 0.567 |
| `npm pack --dry-run` | Passed | 0.417 |
| `uv build --out-dir .jarvis-artifacts/dist` | Wheel and sdist built | 0.967 |
| `logics-manager lint --require-status` | Passed | 0.369 |
| `logics-manager audit --group-by-doc` | 3 unrelated blockers, 15 warnings | 0.517 |
| `python3 .jarvis-artifacts/probe-codex-protocol.py` | Real protocol passed; TUI and interrupt unverified | 4.031 |

The scoped `logics-manager flow validate` invocation for req_083, task_088 and
item_171 returned zero findings. Initial `npm run lint` lacked ruff in the system
interpreter; installing the locked dev extra and activating its PATH resolved it.
Initial `npm test` attempts failed in four existing Git fixture cases because
inherited GIT_DIR, GIT_WORK_TREE and GIT_COMMON_DIR pointed outside their temporary
repositories. Unsetting all three for the test process resolved all four without
changing repository code or Git configuration. The final full suite is green.
A final lint retry also corrected formatting and explicit exception chaining
in the local probe artifact; no production code changed. The global audit
remains failed only for the unrelated blockers listed above.

Timer receipts, local JUnit XML, the bounded Linux probe and build artifacts are
under `.jarvis-artifacts/`, retained outside Git by Jarvis. The Linux probe emits
only a fixed summary and exception type, never raw provider output or credentials.
