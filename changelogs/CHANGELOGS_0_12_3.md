# CDX Manager 0.12.3

## Highlights

- GitHub Releases now trigger an automatic checksum asset workflow so `release-archives.json` is regenerated and uploaded for the published tag.
- `cdx import --force` now preserves detected local Codex plugin state while refreshing sessions from auth-bearing bundles.
- `cdx run` validation errors now explain what is wrong and how to list or create matching sessions.
- Provider capacity or runtime failures now keep failed run records queryable instead of dropping them from the run registry.

## Changes

### Automated release checksum asset

Publishing a GitHub Release now runs `.github/workflows/upload-release-checksums.yml`. The workflow checks out the release tag, regenerates `checksums/release-archives.json`, and uploads it as the `release-archives.json` release asset with replacement enabled for reruns.

### Force import plugin preservation

Auth-bearing force imports now keep local `plugins/` state when the incoming bundle does not include plugin files, so refreshing credentials does not silently remove locally installed Codex plugins.

### More actionable run validation

`cdx run` now returns specific guidance for unknown session references and invalid provider selections so users can recover with `cdx configs`, `cdx add`, or a corrected provider argument.

### Queryable failed provider runs

Provider run failures are now written to the run registry with failure metadata, preserving enough detail for later inspection even when the provider never starts successfully.

## Validation

- `npm run release:validate`
- `npm run lint`
- `npm test`
- `logics-manager lint --require-status`
- `logics-manager audit`
