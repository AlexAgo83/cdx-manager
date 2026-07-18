# CDX Manager 0.11.0

## Highlights

- Fixed Codex structured status parsing so five-hour and weekly reset windows stay mapped to the correct columns.
- Hardened backup import, provider auth probing, release verification, and Windows launcher generation.
- Closed the July 2026 review remediation corpus and follow-up Logics workflow with release-ready validation.

## Changes

### Codex status reset windows

Structured Codex status payloads now preserve the distinction between the five-hour and weekly reset timestamps. `cdx status` no longer mirrors the weekly reset into the five-hour reset column, or the reverse, when provider output includes both windows.

### Safer session import and credentials handling

`cdx import --force` refuses to overwrite existing sessions from bundles without auth payloads unless `--allow-authless-force` is explicitly supplied.

Bundle import now validates selected profile paths, base64 payloads, malformed profile collections, and non-object profile entries before touching existing session profiles. Existing profiles are renamed aside during force import and restored if a per-session import fails.

### Provider auth reliability

Provider auth probes are bounded by a 15 second timeout. Timeouts now surface as a degraded authentication state instead of being persisted as `logged_out`.

Codex interactive launches wait on the per-auth-home lock with a bounded retry instead of running unlocked while another process may be rotating OAuth credentials.

Stored `reasoning_effort` and `power` launch settings now clear each other correctly, so setting one cannot leave the other silently shadowing it.

### CLI robustness and release hardening

`cdx history` skips corrupt JSONL lines, `cdx status` tolerates sessions removed during a concurrent scan, `cdx clean profiles` routes profile cleanup flags consistently, `cdx disk --candidates` validates arguments before scanning, and `cdx view --json` now reports a proper failure when the Logics viewer is unavailable.

The npm launcher routes through the same `cli_entry()` path as the Python entrypoint. Standalone installers and publish workflows now use tagged GitHub Release checksum assets rather than main-branch checksum metadata, and `CDX_ALLOW_UNVERIFIED=1` prints a prominent warning before continuing.

The standalone Windows installer now generates `cdx.cmd` with the installed version directory in the launcher path.

### Logics documentation

The July 2026 review remediation corpus and post-review follow-up corpus are closed with implementation reports, validation evidence, and a clean Logics audit.

## Validation

- `npm run release:validate`
- `npm run lint`
- `npm test`
- `logics-manager lint --require-status`
- `logics-manager audit`
- `git diff --check`
- `npm --cache /private/tmp/cdx-npm-cache pack --dry-run`
- `python -m build`
- `python -m twine check dist/*`
