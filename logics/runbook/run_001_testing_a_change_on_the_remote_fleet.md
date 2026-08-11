## run_001_testing_a_change_on_the_remote_fleet - Testing a change on the remote fleet
> Status: Active
> Category: validation
> Verified: 2026-08-11, preparing v0.18.5 — Python suite in WSL and on Windows, native Windows tray build, graceful stop, and a real companion update between published versions.
> Related request: (none yet)
> Related backlog: (none yet)
> Related task: `task_052_orchestrate_accepted_automatic_cdx_tray_onboarding_and_updates`
> Reminder: Update status, category, verification, and linked refs when you edit this doc.

# Trigger
- A change touches Windows, WSL, or Linux behaviour and the development machine is a Mac. Cross-compilation proves a change builds; it proves nothing about what happens when it runs.
- Before a release, to cover what CI will run only after the tag exists.
- Whenever a defect is suspected to be platform-shaped: five of the defects found while preparing v0.18.5 were invisible from the machine the code was written on.

# Prerequisites
- Host addresses, users and access live in the operator's private `remote-ops` clone, never here. This runbook names roles — "the Windows host", "the WSL distribution" — because a repository that is public should not be an inventory of someone's machines.
- SSH reachable non-interactively: `ssh -o BatchMode=yes -o ConnectTimeout=20 <host> ...`. A password prompt means the check is wrong, not that a password should be typed into a command.
- On the Windows host: a Rust toolchain to build the companion natively, and a Python interpreter to run the suite the way CI does.
- Nothing is installed on the fleet to make a test possible. If a test needs a tool that is not there, that is a finding about the host, not a step.

# Procedure
- **Ship a commit, not a working tree.** `git archive --format=tar HEAD | gzip` to a scratch file, `scp` it over, unpack into a throwaway directory. This avoids pushing a branch to a public remote to test it, and it guarantees the host runs exactly one commit rather than a half-saved editor state.
- **Remember the Windows shell is `cmd.exe`.** `echo a; echo b` runs neither: `;` is not a separator there. Chain with `&&` or `&`, and reach Linux with `wsl.exe -d <distro> -u <user> -- bash -lic "..."`, whose argument must be grouped with escaped double quotes.
- **Watch the login shell.** `wsl.exe -- cdx` is not a login shell and resolves the system PATH, so it can find a different, older tool than the one an interactive terminal resolves. When a version looks impossible, ask `which -a` before believing either answer.
- **Give any test its own HOME.** Export `HOME` and `CDX_HOME` into a scratch directory before running install, consent or update paths. The fleet is someone's working machine, and a test that writes into their real state is a test that cannot be run twice.
- **Prefer a script over nested quoting.** Three levels of shell — ssh, cmd, bash — will mangle anything with quotes in it. Write the script locally, `scp` it, and run it by path. Quoting bugs waste more time than the tests do.
- **Run what CI runs, where CI runs it.** The Python suite in the WSL distribution and again on Windows with the native interpreter; the tray's `cargo test` natively on Windows. CI covers ubuntu and windows, so those two are the ones worth reproducing.
- **Build every published target before tagging.** The asset workflow builds five, two of them musl linked with `rust-lld` and `-C link-self-contained=yes`. A `cargo check` does not link; run the release build for each target locally with the same flags, because a linking failure discovered by the release workflow is discovered after the tag.
- **To see a GUI on Windows, use a temporary scheduled task.** A process started over SSH runs in the SSH session, so a tray icon never appears on the desktop. `schtasks /create ... /it` then `/run` puts it in the interactive session; delete the task immediately afterwards so nothing persists.
- **Ask the operator to look.** Drawing, highlighting, notification attribution and icon promotion are not observable from a shell. Send the exact command, name what to look at, and wait. Three defects in v0.18.5 were found this way and by no other means.
- **Clean up what the test created, and only that.** Scratch trees, archives, temporary scripts and scheduled tasks. Anything that was already on the host — an old tool on the PATH, a running companion — is the operator's to decide about, and is reported rather than removed.

# Verification
- The suite reports the same counts as locally, minus platform-gated skips: on Windows some tests skip by design, and a skip that is silent is a check nobody is doing.
- Every published target links, not merely type-checks.
- A GUI change is confirmed by a person looking at it, quoted in the task's own validation record rather than assumed from a green suite.
- Anything that cannot be tested before publishing is written down as such. For v0.18.5 that was the full `cdx update` between two published releases, and the notification chain as installed — both halves were exercised separately, and saying so is more useful than implying coverage that does not exist.

# Rollback
- Kill any companion started for the test, delete the scheduled task, remove the scratch trees and archives.
- Nothing here modifies the host's own installation, so there is nothing else to undo. If a step ever needs to, it belongs in its own runbook with the operator's confirmation.

# References
- Related request: (none yet)
- Related backlog: `item_085_constrain_wsl_and_linux_tray_support_and_validate_it_on_real_hosts`
- Related task: `task_052_orchestrate_accepted_automatic_cdx_tray_onboarding_and_updates`
- `scripts/tray-smoke.sh` — the companion's own smoke checks, driven by `CDX_TRAY_BIN`
- `adr_005_cdx_tray_runtime_and_companion_transport_boundary`
