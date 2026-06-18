# CDX Manager 0.9.3

## Highlights

- Codex Fast now stays opt-in and no longer silently lowers normal Codex session reasoning effort.
- Codex authentication diagnostics now detect when local credentials belong to a different account than the live CLI session.
- `cdx run` usage parsing now covers the Codex 0.141 JSONL `turn.completed` usage shape, including `reasoning_output_tokens`.

## Changes

### Codex Fast launch behavior

`cdx set <session> --fast on` now marks Fast as a service-tier choice instead of treating it as a reason to lower power to `low`. Normal Codex sessions continue to launch with their configured reasoning effort and an explicit flex service tier when Fast is off.

### Codex auth isolation diagnostics

`cdx doctor` now reads the email from local Codex tokens and compares it with the live `codex login status` account when both are available. If a managed session has local tokens for one account but the CLI is authenticated as another, the report surfaces a repairable `codex_auth_mismatch` issue instead of reporting a vague live-auth failure.

The auth probe also avoids trusting local credentials alone for launch and run readiness, which keeps multi-account sessions from accidentally using the wrong global Codex login after a CLI update or account switch.

### Codex 0.141 run usage parsing

Codex CLI 0.141 emits headless usage in JSONL `turn.completed` events. `cdx run` now maps the current `reasoning_output_tokens` field into the stable `reasoning_tokens` output and keeps computing total tokens from input plus output when the provider omits `total_tokens`.

## Validation

- `cdx doctor --json`
- `cdx status --json --refresh`
- `cdx run --provider codex --cwd /Users/alexandreagostini/Documents/cdx-manager --prompt 'Reply exactly: CDX_CODEX_OK' --timeout-seconds 90 --json`
- `cdx run --provider claude --cwd /Users/alexandreagostini/Documents/cdx-manager --prompt 'Reply exactly: CDX_CLAUDE_OK' --timeout-seconds 90 --json`
- `npm run lint`
- `npm test`
- `logics-manager lint --require-status`
- `logics-manager health`
- `git diff --check`
