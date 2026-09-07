# CDX Manager 0.20.10

## Fixes

- Keep the local account when `cdx import --merge` brings in a bundle that
  carries authentication. A keychain-backed profile has no credential file, so
  the collision was never noticed and the local login was replaced and its
  keychain entry deleted by an operation whose whole promise is to keep local
  values. The collision is now resolved against the keychain itself, and the
  import says which sessions kept their existing Claude authentication.
- Restore the destination's Claude credential when `cdx import --force` fails
  after staging the imported one. Filesystem rollback already worked; the
  keychain entry did not come back, which lost the profile's only login. It is
  snapshotted before anything can clear it and restored on failure, and a
  recovery that cannot complete now names Claude keychain authentication
  instead of reporting a generic incomplete recovery.
- Decode encrypted bundles with the key derivation function their exporter
  recorded. A bundle written on a Python without `hashlib.scrypt` stopped
  opening on a Python that has it, with the same passphrase, because decoding
  re-chose the derivation from the importing runtime. A derivation this runtime
  cannot compute is now reported as such rather than as a wrong passphrase, and
  older bundles that recorded nothing usable stay readable.
- Keep every accepted note when several agents append to the same `cdx memory`
  scope at once. The append read the scope and wrote it back with nothing
  covering the pair, so both callers were told their note was accepted and one
  of them was not there.
- Make `cdx run --detach` actually run. The child was asked for a CLI module
  that does not exist, so the launcher reported a run id for work that never
  started and never cleaned up its staged prompt. A module name that does not
  resolve now fails the launch instead of being reported as launched.
- Terminate the provider when a headless run is interrupted. Ctrl-C unwound the
  supervising CLI and left the provider running in its own process group, still
  consuming quota and writing to the working tree, while the run record
  described the supervisor. The provider tree is now terminated and reaped, and
  the run is recorded as `cancelled` with exit code 130, which a caller can tell
  apart from a failure and from a timeout.
- Keep a working tray when replacing the companion fails midway. A filesystem
  error between retiring the installed companion and promoting the staged one
  left the install record pointing at a path with nothing in it, and skipped the
  restart of the tray that had just been stopped. The proven companion is put
  back and the tray is restarted on it.
- Keep the Windows Start Menu shortcut pointing at the companion that is
  actually installed. It was written against the staged executable, which the
  update then moved, and the promoted install record dropped it, so uninstall
  stopped removing it. It is now written by the promotion against the final
  path and stays owned by uninstall.
- Make the macOS pre-promotion launch check real. `--print` was handed to the
  `open` utility rather than to the companion and the exit status was ignored,
  so the gate passed for an app bundle that never started. It now runs the
  binary inside the bundle, refuses a bundle with nothing runnable in it, and
  still accepts a companion that started and reported a problem of its own.
- Open the intended command when a Windows tray reaches CDX through WSL.
  A session's launch settings row sent `config <session>` as a single argument,
  so CDX saw one session name with a space in it and refused it.
- Offer only terminals a Windows tray can open. The candidate list is built by
  whichever host answers the poll, which under WSL is Linux, so the menu could
  offer a Linux terminal and then open nothing when it was chosen. The
  companion now lists what it can launch, and a stored preference it cannot
  open falls back to the default console instead of an inert click.
- Run the selected command when the tray terminal preference is `cmd`. It was
  given PowerShell's `-NoExit -Command`, which `cmd.exe` accepts without
  running anything, so the click opened an idle shell.

## Notes

- A cancelled headless run is a new terminal state: `cancelled`, alongside
  `succeeded`, `failed` and `timed_out`. Callers that branch on run status
  should treat it as an outcome rather than as an unknown value.
- Bundles exported by this version record and honour their key derivation
  function. Bundles exported by earlier versions are unaffected and stay
  readable.
