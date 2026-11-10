# CDX Manager 0.26.13

Release date: 2026-11-10

## Breaking changes

- Python 3.10 or newer is now required. Python 3.9 reached end of life in
  October 2025; packaging, installation guidance and CI no longer support it.
  Development dependencies require pytest 9.0.3 or newer, which closes
  Dependabot alert #2 (pytest tmpdir handling) (`870d69c`).

## Improvements

- `cdx sessions --json` keeps every existing profile field and adds a
  `processes` list with one entry per running agent process: the agent PID,
  the wrapper PID when there is one, the current conversation ID with its
  source (Claude's per-PID session file is read on every call, so `/clear` and
  several agents on one profile are visible), the launch conversation ID, the
  working directory and the start time (#132, `f5e5429`).
- `cdx run --isolate-workspace --ro-input NAME=PATH` mounts an owner-controlled
  directory read-only under `/opt/inputs/` and exposes its sandbox path in the
  variable `NAME`. Invalid, reserved or duplicate names, missing directories,
  top-level symlinks, foreign ownership and paths overlapping the workspace,
  configuration, state or credentials are refused. Inputs persist through
  detached runs and continuations and are revalidated before launch;
  `cdx schema --json` advertises `capabilities.ro_inputs = 1` (`58b7047`).

## Maintenance

- Use neutral host and project names in documentation and test fixtures
  (`dd19c68`).
