# CDX Manager 0.9.4

## Highlights

- Added provider-native resume commands for named sessions.
- Added a non-launching capability check for resume support.
- Closed the Logics workflow for the resume command delivery.

## Changes

### Provider-native resume commands

`cdx` can now resume supported provider conversations without requiring users to remember provider-specific commands:

```
cdx main -r
cdx main --resume
cdx resume main
```

Codex sessions resume with `codex resume --last --cd <cwd>` inside the named session's isolated `CODEX_HOME`. Claude sessions resume with `claude --continue --name <name>` inside the named session's isolated `HOME`.

Providers without a verified native resume mode, currently Antigravity and Ollama, return a clear unsupported result instead of falling back to a normal launch.

### Resume capability checks

`cdx can-resume <name>` reports whether a session can resume without launching an interactive provider. JSON mode exposes a provider-neutral payload with the session name, provider, resumable state, strategy, reason, and command preview.

### Workflow traceability

The Logics request, backlog item, task, and ADR for provider-native resume are complete, with validation evidence attached to the delivery task.

## Validation

- `python -m unittest discover -s test -p 'test_runtime_py.py' -k resume`
- `python -m unittest discover -s test -p 'test_cli_py.py' -k resume`
- `python -m unittest discover -s test -p 'test_cli_py.py' -k help`
- `python -m unittest discover -s test -p 'test_*_py.py' -k resume`
- `npm run lint`
- `npm test`
- `logics-manager lint --require-status`
- `logics-manager audit`
- `git diff --check`
