# CDX Manager 0.9.1

## Highlights

- `cdx view` now forwards all `logics-manager view` flags instead of rejecting them.
- Fixes a silent PATH resolution bug that could prevent `logics-manager` from being found.

## Changes

### cdx view: full flag passthrough

`cdx view` previously accepted only `--json` and raised a usage error for every other argument. All `logics-manager view` flags are now supported and forwarded transparently:

- `--lan` / `--lan-rw` — expose the viewer on the local network
- `--focus <ref>` / `--read` — open the viewer centered on a workflow document
- `--port <port>` / `--host <host>` — bind to a custom address
- `--refresh-interval <s>` — override the auto-refresh interval
- `--tls` / `--tls-cert <path>` / `--tls-key <path>` — serve over HTTPS
- `--open` / `--no-open` — control browser auto-open

### Bug fixes

- `resolve_logics_manager`: `shutil.which` was called with `path=""` when `env` had no `PATH` key, causing it to search nothing and always return `None`. Now falls back to the process PATH.
- `run_logics_viewer`: the viewer subprocess now inherits the full OS environment (`os.environ` merged with any `env` overrides) instead of receiving a partial dict that stripped all inherited variables.

### Docs

- README command table and feature description updated to list all forwarded viewer flags.
- `LOGICS_PROMPT` updated to reference `cdx view` instead of `logics-manager view` directly.

## Validation

- `npm run prepublishOnly`
- `npm pack --dry-run`
- `logics-manager lint --require-status`
- `logics-manager audit --legacy-cutoff-version 1.1.0 --group-by-doc`
