# CHANGELOGS_0_3_2

Release date: 2026-04-16

## CDX Manager 0.3.2

CDX Manager 0.3.2 updates the npm release workflow to use the npm CLI version required for Trusted Publishing.

### Packaging

- Runs the npm publish workflow on Node 24.
- Installs npm 11 before publishing so GitHub Actions OIDC trusted publishing is supported.
- Keeps npm, PyPI, GitHub Releases, pipx, uv, and the standalone installer aligned on the same release version.

### Validation

```bash
npm run lint
npm test
npm --cache /tmp/cdx-npm-cache publish --dry-run
```
