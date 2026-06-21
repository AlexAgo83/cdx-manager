# CDX Manager 0.9.6

## Highlights

- Kept Claude launch authentication separate from Claude quota-refresh failures.
- Reduced periodic update-check caching from 12 hours to 1 hour.

## Changes

### Claude auth stays usable after quota refresh errors

`cdx status --refresh` no longer marks a Claude session as logged out when the Anthropic quota-refresh request returns an authentication error but the Claude CLI auth probe succeeds.

This keeps `cdx <session>` launch readiness tied to `claude auth status`, while still surfacing quota-refresh failures as warnings for status and automation.

### Hourly update checks

Periodic update checks now reuse cached release data for 1 hour instead of 12 hours. The same interval applies to both the `cdx-manager` release check and the companion `logics-manager` update check.

## Validation

- `python3 -m unittest discover -s test -p 'test_update_check_py.py'`
- `python3 -m unittest discover -s test -p 'test_*.py' -k 'claude_auth'`
- `python3 -m unittest discover -s test -p 'test_*.py' -k 'login_claude'`
- `npm run lint`
- `npm test`
- `cdx status claw --json --refresh`
