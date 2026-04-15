# Contributing to cdx

## Getting Started

```bash
git clone <repo>
cd cdx-manager
make install
```

Run the test suite before making any changes to establish a clean baseline:

```bash
npm test
npm run lint
```

## Workflow

1. Create a branch from `main`.
2. Make your changes.
3. Run the full local validation pipeline (see below).
4. Open a pull request against `main`.

## Local Validation

Run before every commit:

```bash
npm run lint
npm test
```

Both commands must pass with no errors before opening a pull request.

## Code Style

- No runtime dependencies. Keep the install footprint at zero.
- All I/O goes through `stdout`/`stderr` options passed into `main()`, never directly to `sys.stdout`. This keeps every command unit-testable without spawning a subprocess.
- Errors use `CdxError` from `src/errors.py`. Set `exit_code` when a specific exit code matters.
- Do not add comments for self-evident code. Add a comment only when the logic is non-obvious.

## Tests

Tests use Python's built-in `unittest` runner.

Test files live under `test/` and follow the `test_*_py.py` naming convention.

When adding a new command or changing existing behavior, add or update the corresponding test in `test/test_cli_py.py` or `test/test_session_service_py.py`.

## Adding a Provider

Providers are declared in `src/session_service.py` (`ALLOWED_PROVIDERS`). Adding a new provider requires:

1. Adding the provider name to `ALLOWED_PROVIDERS`.
2. Handling the new provider in `_build_launch_spec`, `_build_login_status_spec`, and `_build_auth_action_spec` in `src/cli.py`.
3. Adding test coverage for the new launch and auth paths.

## Reporting Issues

Open an issue with:

- the command you ran
- the full error output
- the version (`cdx --version`)
- the provider and OS
