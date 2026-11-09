# CDX Manager 0.26.11

Release date: 2026-11-09

## Improvements

- `cdx run --continue-run` accepts a permissions-only Claude `--settings`
  (#129, `3a7f8c8`), from profile or per-run extra arguments, in separate or
  `=` syntax, as inline JSON or a UTF-8 file. The validated object is passed
  inline so the file cannot change before launch. Any other settings key
  (model, effort, env, hooks and the like) is still refused with its name and
  `continue_run_settings_mismatch`, as are unreadable files, invalid JSON and
  non-object values. Continued runs therefore keep the same allowlist as fresh
  ones instead of falling back to auto mode.

## Maintenance

- Record tray companion checksums for v0.26.10 (`e72de79`).
- Record release archive checksums for v0.26.10 (`740de2c`).
