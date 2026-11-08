# Local isolated Claude setup-token selection — mission e4e911c659

Fixes #124: a full claude.ai login must not hide an existing setup token from a
local `cdx run --isolate-workspace` launch. The local sandbox launch boundary reads
`credentials/default.json` directly for isolation and uses the ordinary login
precedence otherwise. The sandbox's environment allowlist receives only the
setup token value; no profile credential file, full-login access token or refresh
token is exposed. The setup credential file itself is not mounted either.

If the stored setup token is missing or unreadable, fail before provider startup
with `isolated_claude_token_missing` and guidance to run `cdx login <profile>` or
choose a setup-token profile. Conservative assumption: ambient OAuth credentials
are not a substitute for a profile's stored setup token. Remote Claude retains
its separate dedicated-token transport and storage contract.

This is a bounded correction at the authentication declaration under ADR 030:
the nearby comment and CLI regressions record the reason without a new workflow
chain. Regression coverage in `test/test_commands_runs_py.py` exercises a full
login plus stored setup token through the real sandbox command builder, checks
that neither login credentials nor profile mounts reach the child, preserves
ordinary headless login precedence, and refuses a full-login-only profile even
when an ambient token exists. All credentials in new fixtures are fake.

Validation commands are timed by `.jarvis-input/mission-test-runner.py`; receipts
remain outside the published source. Authenticated inference requires operator
credentials and is not established by synthetic child-process tests. Complete
green required GitHub CI on the merged commit remains mandatory before merge.
