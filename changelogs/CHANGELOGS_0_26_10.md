# CDX Manager 0.26.10

Release date: 2026-11-08

## Improvements

- Isolated Claude runs accept a profile with a full claude.ai login when it
  also stores a setup token (#124, `66ee94b`). `cdx run <profile>
  --isolate-workspace` uses only the stored setup token; the full-login
  credentials and refresh tokens are never mounted or passed into the sandbox.
  Without a setup token the run is still refused before the provider starts.
- Continue an isolated run (#122, `1483f03`). `cdx run <profile>
  --continue-run RUN_ID` now accepts a parent started with
  `--isolate-workspace` and resumes it inside isolation with the parent's
  network and mount boundary, which is never widened. Only the conversation
  transcripts are retained under `CDX_HOME/isolated-runs/RUN_ID/`. A missing
  or replaced workspace is refused with `continue_run_workspace_gone`, so
  callers can fall back to a fresh run.

## Maintenance

- Record tray companion checksums for v0.26.9 (`1dcd6d7`).
- Record release archive checksums for v0.26.9 (`9b50da6`).
