# CDX Manager 0.9.2

## Highlights

- `cdx import` gains a `--merge` flag to fill in missing data without overwriting what already exists locally.

## Changes

### cdx import: `--merge` mode

`cdx import` previously offered two stances on existing sessions: reject the conflict (default) or erase and replace (`--force`). A third mode is now available:

```
cdx import backup.cdx --merge
```

With `--merge`, for each session that already exists locally:

- **Session fields** — existing values are kept; fields absent locally are pulled in from the bundle.
- **Session state** — same merge rule: local data wins, bundle fills the gaps.
- **Profile files** (auth.json, credentials, etc.) — files that already exist on disk are left untouched; files missing locally are restored from the bundle.
- **New sessions** in the bundle that have no local counterpart are imported normally.

`--force` and `--merge` are mutually exclusive and raise a clear error if combined.

## Validation

- `npm run prepublishOnly`
- `npm pack --dry-run`
- `logics-manager lint --require-status`
- `logics-manager audit --legacy-cutoff-version 1.1.0 --group-by-doc`
