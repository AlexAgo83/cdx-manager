# Remote control validation

The CI test job runs the full fake-provider suite on `ubuntu-latest`,
`macos-latest` and `windows-latest`, with a 20 minute limit per matrix job.
Each job uploads `test-results/pytest.xml`, including on failure, as
`pytest-<os>-py3.11`. A configured matrix is not evidence of three passing runs.
Green GitHub CI on the merged commit remains mandatory before merge.

The portable stream fake uses a reader thread and a queue instead of selecting
on a pipe. Tests cover owner-only endpoint access, idle queueing, the legacy
Claude stream interrupt and resume, current Claude channel Escape delivery,
Codex initialization, thread selection, sending, interruption and event mapping.
The Codex dialogue test replaces the WebSocket transport; the separate socket
roundtrip test covers framing. Neither establishes authenticated provider behavior.
The inherited Antigravity test for Claude message merging is intentionally skipped.

## Authenticated manual checks

Run on Linux, macOS and Windows using disposable profiles and an empty trusted
working directory. These checks make real provider calls. Use an interactive
terminal and a second terminal with the same `CDX_HOME`. The examples assume its
default location and unused profile names. Authenticate through the provider's
interactive login. Never paste credentials into arguments or record login output.
Do not read or attach endpoint files, capability files, auth files or environments.
Record only OS, CLI versions, commands, event kinds and the harmless replies below.

From the checkout root, prepare profiles (commands work in bash and PowerShell):

```text
node bin/cdx.js add claude remote-claude
node bin/cdx.js add remote-codex
node bin/cdx.js login remote-claude
node bin/cdx.js login remote-codex
node bin/cdx.js set remote-claude --remote-control on
node bin/cdx.js set remote-codex --remote-control on
claude --version
codex --version
```

### Linux and macOS

Launch `node bin/cdx.js remote-claude` in terminal A. In tmux, accept the
channel development warning if needed. Outside tmux accept it manually; channel
interrupt delivery requires tmux, so repeat the interrupt check in tmux.
Type a harmless context marker in the TUI and wait until it is idle. In terminal B:

```bash
node bin/cdx.js send remote-claude --status --json
printf '%s\n' 'Remember the marker REMOTE_FAKE_CHECK and reply READY.' | node bin/cdx.js send remote-claude --stdin
printf '%s\n' 'What marker did I ask you to remember?' | node bin/cdx.js send remote-claude --stdin
printf '%s\n' 'Count slowly from one to one hundred, one number per line.' | node bin/cdx.js send remote-claude --stdin
node bin/cdx.js send remote-claude --interrupt
printf '%s\n' 'Reply BACK and repeat the marker.' | node bin/cdx.js send remote-claude --stdin
```

Wait for each normal reply; interrupt while the long turn is visibly running.
Confirm the TUI remains usable, replies retain the marker and the interrupted
turn stops. Repeat with terminal A running `node bin/cdx.js remote-codex` and
these exact terminal B commands:

```bash
node bin/cdx.js send remote-codex --status --json
printf '%s\n' 'Remember the marker REMOTE_FAKE_CHECK and reply READY.' | node bin/cdx.js send remote-codex --stdin
printf '%s\n' 'What marker did I ask you to remember?' | node bin/cdx.js send remote-codex --stdin
printf '%s\n' 'Count slowly from one to one hundred, one number per line.' | node bin/cdx.js send remote-codex --stdin
node bin/cdx.js send remote-codex --interrupt
printf '%s\n' 'Reply BACK and repeat the marker.' | node bin/cdx.js send remote-codex --stdin
```

### Windows PowerShell

Launch `node bin/cdx.js remote-claude` in terminal A and accept the development
channel warning. Type a harmless context marker in the TUI and wait until idle.
In terminal B:

```powershell
node bin/cdx.js send remote-claude --status --json
'Remember the marker REMOTE_FAKE_CHECK and reply READY.' | node bin/cdx.js send remote-claude --stdin
'What marker did I ask you to remember?' | node bin/cdx.js send remote-claude --stdin
'Count slowly from one to one hundred, one number per line.' | node bin/cdx.js send remote-claude --stdin
node bin/cdx.js send remote-claude --interrupt
'Reply BACK and repeat the marker.' | node bin/cdx.js send remote-claude --stdin
```

The current Claude channel sends Escape through tmux only. Native Windows without
tmux cannot prove interrupt delivery: record that limitation, interrupt manually
and leave the automated interrupt acceptance check open. Do not count a successful
queue acknowledgement as proof that the turn stopped.

Repeat with terminal A running `node bin/cdx.js remote-codex` and terminal B:

```powershell
node bin/cdx.js send remote-codex --status --json
'Remember the marker REMOTE_FAKE_CHECK and reply READY.' | node bin/cdx.js send remote-codex --stdin
'What marker did I ask you to remember?' | node bin/cdx.js send remote-codex --stdin
'Count slowly from one to one hundred, one number per line.' | node bin/cdx.js send remote-codex --stdin
node bin/cdx.js send remote-codex --interrupt
'Reply BACK and repeat the marker.' | node bin/cdx.js send remote-codex --stdin
```

### Evidence and cleanup

Review only each disposable profile's `*.events.jsonl` files in
`<CDX_HOME>/state/remote/`. Confirm `ready`, `queued`, `working`, assistant text and
`done`; Codex must also report `interrupted`. Claude channel interruption comes
from its transcript; confirm the actual stopped turn and recovery in the TUI.
Verify context across messages, queueing while busy, keyboard input after remote
turns and a clean exit with `ended`. No endpoint or capability secret may appear
in process arguments or event logs. Record a sanitized result for each platform
in item_171. Historical Linux Antigravity evidence does not replace a current
Claude channel or Codex check.

Exit the TUIs normally and confirm the endpoint is gone by running
`node bin/cdx.js send remote-claude --status --json` and
`node bin/cdx.js send remote-codex --status --json`: both must report no active
endpoint. These expected nonzero results are manual cleanup assertions.

```text
node bin/cdx.js rmv remote-claude --force
node bin/cdx.js rmv remote-codex --force
```
