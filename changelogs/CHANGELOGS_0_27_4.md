# CDX Manager 0.27.4

Release date: 2026-11-13

## Improvements

- Every remote-control event line carries the launcher `pid`, and each launch
  also writes its own `<name>@<pid>.events.jsonl` (the shared
  `<name>.events.jsonl` is still written). The remote error log becomes
  `<name>@<pid>.remote.err`. The format is documented under "Remote-control
  state files" in `docs/cli.md` (#145).

## Fixes

- Closing the terminal that hosts a launch (SIGHUP, as `tmux kill-session`
  sends, or SIGTERM) no longer leaves its remote-control files behind: the
  launcher stops its TUI and remote run, removes its own endpoint and token,
  hands the pointer to another live launch and records an `ended` event with
  the signal (#145).
