# CDX Manager 0.9.5

## Highlights

- Made per-session status lookup targeted instead of resolving every configured session.
- Added fast status controls for automation-heavy workspaces.
- Added a Logics release contract for the `cdx-manager` release workflow.

## Changes

### Faster per-session status

`cdx status <name>` now resolves only the named session. Previously the command collected all status rows and filtered afterward, so a detail lookup could still trigger live probes for every configured session.

### Cached and bounded status probes

`cdx status --cached` reads stored status only and skips live provider probes. This is intended for AGENTS prompts, health checks, and project scripts that need a quick snapshot without risking provider timeouts.

Live Codex status probes can also be bounded with:

```
cdx status --timeout 1
CDX_STATUS_TIMEOUT_SECONDS=1 cdx status
```

The timeout applies to Codex live rate-limit probes while preserving the existing cached and fallback behavior.

### Release workflow contract

The repository now includes `logics/release/contract.json` and `logics/release/release-contract.v1.schema.json`. The contract records the expected version sources, changelog path, checksum gate, validation commands, GitHub release gate, npm publication, and PyPI publication checks.

## Validation

- `python -m unittest discover -s test -p 'test_session_service_py.py'`
- `python -m unittest discover -s test -p 'test_cli_py.py' -k 'status'`
- `npm run lint`
- JSON Schema validation for `logics/release/contract.json`
- `logics-manager lint --require-status`
- `logics-manager audit`
- `git diff --check`
- `node bin/cdx.js --version`
- `python3 bin/cdx --version`
- `npm --cache /private/tmp/cdx-npm-cache pack --dry-run`
- `python -m build`
- `python -m twine check dist/*`
