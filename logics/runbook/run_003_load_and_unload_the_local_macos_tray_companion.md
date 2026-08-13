## run_003_load_and_unload_the_local_tray_companion - Load and unload the local tray companion
> Status: Active
> Category: support
> Verified: 2026-08-13: load and unload passed against the local development and installed macOS companions.
> Related request: (none yet)
> Related backlog: (none yet)
> Related task: (none yet)
> Reminder: Update status, category, verification, and linked refs when you edit this doc.

# Trigger
- A macOS or Windows tray change needs a real menu-bar smoke test against the working tree.
- The installed companion must be restored after local testing without replacing
  or reinstalling its release bundle.

# Prerequisites
- Run from a CDX checkout on macOS or Windows with Rust, Node, and Python available.
- An installed companion is optional for `load`, but required for `unload`.
- Close an open tray menu before either command so the running companion can
  consume its bounded graceful-stop request.

# Procedure: macOS
From the repository root, load a freshly built development companion:

```sh
./scripts/tray-dev.sh load
```

The command builds `tray/target/release/CDX.app` with `--dev`, stops the
lock-verified running companion, starts the local bundle with `CDX_TRAY_CDX`
pointing at `bin/cdx`, then verifies that the running process is the local
bundle. It does not alter the installed companion or its autostart setting.

When the local test is finished, restore the installed companion:

```sh
./scripts/tray-dev.sh unload
```

This stops whichever lock-verified companion is running, starts the companion
recorded in the CDX install state, and verifies that the process path is under
`.cdx/tray/companion/CDX.app`.

# Procedure: Windows

From a PowerShell session in the checkout, use the equivalent helper:

```powershell
.\scripts\tray-dev.ps1 load
```

It builds `tray\target\release\cdx-tray.exe`, writes a local `.cmd` wrapper
that invokes the checkout's `node bin\cdx.js`, stops only the lock-verified
companion, then verifies the running process is the development executable.
It does not install or overwrite a release companion.

After testing, restore an already installed companion:

```powershell
.\scripts\tray-dev.ps1 unload
```

`unload` intentionally fails when no release companion is installed; install
state is never guessed and a development test must not create it.

The companion needs the interactive Windows desktop session. An SSH shell runs
in session 0 and the helper refuses it. For a remote smoke test, invoke the
helper from the active user's desktop session; a temporary scheduled task with
the user's `InteractiveToken` is acceptable, but delete that task immediately
after it starts the companion.

To exercise a Windows companion against CDX in WSL, set the transport and the
absolute Linux executable before `load`; the helper preserves this explicit
override instead of substituting its native checkout wrapper:

```powershell
$env:CDX_TRAY_WSL = '1'
$env:CDX_TRAY_WSL_DISTRO = 'Ubuntu'       # omit to use the WSL default
$env:CDX_TRAY_CDX = '/home/aagos/.local/bin/cdx'
.\scripts\tray-dev.ps1 load
```

# Verification
- `load` prints `Development tray loaded` only after the process command is
  `tray/target/release/CDX.app/Contents/MacOS/cdx-tray`.
- `unload` prints `Installed tray restored.` only after the process command is
  the recorded installed bundle. Confirm independently when needed:

```sh
cdx tray doctor
```

- A development bundle is ad-hoc signed. macOS can forget its notification
  permission after a rebuild; this is expected and does not change the
  installed companion's release signing identity.
- On Windows, confirm the running executable with `cdx tray doctor` and use
  the tray menu to exercise the platform-specific launch branch.

# Rollback
- Run `./scripts/tray-dev.sh unload` on macOS or `.\scripts\tray-dev.ps1 unload`
  on Windows. If `load` fails after it stopped the
  current companion, the same command returns directly to the installed one.
- Do not use `cdx tray install` or replace anything under `.cdx/tray/companion`
  for this workflow: the release bundle is intentionally left untouched.

# References
- `scripts/tray-dev.sh`
- `scripts/tray-dev.ps1`
- `scripts/build-tray.sh`
- `docs/tray-local-testing.md`
- `src/tray_restart.py`
- `adr_005_cdx_tray_runtime_and_companion_transport_boundary`
