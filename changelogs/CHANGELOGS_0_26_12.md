# CDX Manager 0.26.12

Release date: 2026-11-10

## Fixes

- `cdx run --continue-run` with a Claude `--settings` allowlist larger than
  512 characters no longer fails at launch with "Extra args contain unsupported
  characters" (#131, `958dccc`). The validated permissions-only settings are
  copied into a private run-state file (mode 0600, atomic write) and Claude
  receives its path instead of inline JSON, so the launch argument limit and
  character checks keep protecting user-supplied arguments unchanged. The copy
  holds the content at continue time, is removed with the run state and is
  mounted read-only for isolated continuations.

## Maintenance

- Record tray companion checksums for v0.26.11 (`19143b2`).
- Record release archive checksums for v0.26.11 (`2e1fe78`).
