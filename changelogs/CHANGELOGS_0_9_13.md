# CDX Manager 0.9.13

## Highlights

- Fixed Claude `setup-token` capture on Linux by using the util-linux `script` flush flag.

## Changes

### Claude setup-token capture

Linux terminals now run transcript capture with `script -f` instead of the BSD/macOS-only `script -F` spelling.

This prevents util-linux `script` from exiting with `invalid option -- 'F'`, which previously made `cdx` fall back to running `claude setup-token` without transcript capture and miss the printed token.

macOS keeps the existing `script -F` behavior.

## Validation

- `npm run release:validate`
- `npm run lint`
- `npm test`
- `logics-manager lint --require-status`
- `logics-manager audit`
- `git diff --check`
- `npm --cache /private/tmp/cdx-npm-cache pack --dry-run`
- `python -m build`
- `python -m twine check dist/*`
