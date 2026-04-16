# CHANGELOGS_0_3_1

Release date: 2026-04-16

## CDX Manager 0.3.1

CDX Manager 0.3.1 is a release-channel synchronization update.

### Packaging

- Uses npm Trusted Publishing through GitHub Actions OIDC instead of long-lived npm tokens.
- Keeps npm, PyPI, GitHub Releases, pipx, uv, and the standalone installer aligned on the same release version.
- Retains the Python-native packaging and standalone install support introduced in 0.3.0.

### Validation

```bash
npm run lint
npm test
npm --cache /tmp/cdx-npm-cache publish --dry-run
python -m build
python -m twine check dist/*
```

### Notes

- This release exists because the npm Trusted Publishing workflow was added after the `v0.3.0` tag. A fresh release is required for GitHub Actions to run the updated workflow definition for npm publishing.
