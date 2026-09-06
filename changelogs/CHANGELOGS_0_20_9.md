# CDX Manager 0.20.9

## Fixes

- Preserve an existing session when `cdx import --merge` fails. The profile,
  its record and its state are snapshotted first — symlinks kept as links —
  and restored on failure; if recovery itself fails, the error names the
  retained recovery directory instead of leaving the session destroyed.
  Bundle paths that escape the profile through a link are refused.
- Stop `cdx cp` from copying the profile's macOS keychain directory. Only the
  source profile's own keychain entry is transferred, and an overwritten
  destination entry is restored if the copy fails.
- Keep Claude authentication working across `cdx ren`. The destination
  keychain entry is staged before the profile moves, an existing destination
  entry is refused, and a failed cleanup of the old entry is reported once the
  renamed session is already usable.
- Delete a session's Claude keychain credential when the session is removed,
  so the OAuth token does not outlive the profile and the freed name can be
  reused by `cdx cp` and `cdx ren`.
- Refresh Claude quota from the profile-scoped keychain entry before falling
  back to legacy credential files, so keychain-authenticated sessions no
  longer read as missing credentials. An unreadable keychain is an explicit
  error, never a silent "not logged in" — unless a credential file on disk
  can still answer, in which case `cdx` uses it and says nothing.

- Export keychain-backed Claude authentication. `cdx export --include-auth`
  carries the profile's keychain entry in the encrypted bundle as its
  credential file, and `cdx import` restores a usable login, replacing any
  entry the destination profile already had so the imported credential is the
  one in effect. A keychain that cannot be read is an explicit error before
  anything is written, in both text and JSON, so an existing `--force`
  destination survives it.

## Notes

- A credential restored from a bundle lands in the profile's credential file
  rather than the keychain; Claude Code moves it back on its next launch.
- Merge imports temporarily need room for a second copy of the profile being
  merged into.
