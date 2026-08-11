## run_002_finding_out_which_cdx_and_which_home_you_are_talking_to - Finding out which CDX and which home you are talking to
> Status: Active
> Category: support
> Verified: 2026-08-11, three separate incidents in one day — a notification delivered directly while a tray was listening, a tray told to update a CDX that was current, and `cdx update` reporting success while the installation it was meant to replace stayed where it was.
> Reminder: Update status, category, verification, and linked refs when you edit this doc.

# Trigger
- Something reports success and nothing observable changes.
- Two commands disagree about the version: `cdx --version` says one thing, a companion or a hook behaves like another.
- An alert arrives through the direct path while a tray is plainly running, or a tray shows nothing while alerts are plainly being produced.
- Any question of the form "why is it not using the one I installed".

# Prerequisites
- Nothing but a shell. Every check here is read-only, and none of them needs a password or a running session.

# Procedure
CDX has three independent ways to mean a different thing than the one in front
of you. They compose, which is why the symptom is usually "it worked and
nothing happened".

- **A redirected `HOME` is the normal state inside a session.** CDX gives each
  session its own home so provider auth stays isolated, so a command run *from
  inside* a session resolves `~` to that profile. `echo $HOME` is the first
  question: a path under `profiles/<name>/` means everything home-relative —
  `~/.cdx`, `~/.local`, `~/.config` — belongs to that session and not to you.
  This is what makes `cdx update` install correctly into a copy nobody runs.

- **`CDX_HOME` decides which store a hook writes to.** It is pinned at session
  launch from the launching shell's environment, so a session started from
  inside another session inherits the inner home. A hook then looks for a tray
  heartbeat in a store the companion never writes to, finds none, and delivers
  the notification itself — correctly, and to the surprise of everyone. Compare
  `ls ~/.cdx/tray/heartbeat.json` against the store the companion is beating
  into before concluding the tray is broken.

- **PATH resolves differently for a non-login shell.** A tray companion crossing
  into WSL runs `wsl.exe -- cdx`, which does not read a login profile, so it
  resolves the system PATH and can find an older install that an interactive
  terminal never sees. `which -a cdx` lists them all; the first line is the one
  that answers. `CDX_TRAY_CDX` names the one you meant.

- **A working directory can decide what a command reports.** Anything that reads
  a repository — the Logics tray card, `cdx view` — answers about the directory
  it runs in. A companion started at login has no meaningful one, so a check run
  by hand from a project and the same check run by the companion are two
  different questions.

Run these four in order and the answer is usually obvious by the second:

```sh
echo "$HOME"                 # a profiles/ path means you are inside a session
echo "${CDX_HOME:-$HOME/.cdx}"
which -a cdx                 # more than one line is the whole explanation
pwd                          # for anything that reads a repository
```

# Verification
- The version reported by the binary on PATH matches the version of the
  directory the symlink points at, and both match the store being written to.
- A tray that is listening has a heartbeat under the same `CDX_HOME` the hook
  resolves. If the paths differ, the direct notification is correct behaviour
  and the tray is not at fault.
- After an update, the new version directory exists under the intended prefix.
  A successful installer that created nothing new almost always installed
  somewhere else, not nowhere.

# Rollback
- Nothing here changes anything. If a diagnosis leads to re-running an install
  with an explicit `HOME` or `PREFIX`, the previous version directories are all
  still present and a symlink can be pointed back at any of them.

# References
- Related backlog: `item_086_deliver_structured_private_hook_context_to_actionable_tray_alerts`
- `src/agent_notify.py` — `launch_notify_env`, which documents why `CDX_HOME` is pinned rather than inherited
- `adr_005_cdx_tray_runtime_and_companion_transport_boundary`
- `run_001_testing_a_change_on_the_remote_fleet`
