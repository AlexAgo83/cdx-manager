# Changelog (`0.2.0 -> 0.2.1`)

Release date: 2026-04-16

## CDX Manager 0.2.1

CDX Manager 0.2.1 prepares the package for npm publication.

### Packaging

- Removed the private package flag so npm publication is possible.
- Added npm package metadata: license, author, repository, bugs, homepage, keywords, and Node engine declaration.
- Added `prepublishOnly` so `npm publish` runs lint and tests before publication.
- Normalized the `bin.cdx` path with `npm pkg fix`.
- Documented the future npm install command in the README.

### Validation

```bash
npm run lint
npm test
npm --cache /tmp/cdx-npm-cache publish --dry-run
npm view cdx-manager name version --registry https://registry.npmjs.org/
```

### Notes

- `npm view cdx-manager` currently returns `E404`, so the package name appears available on the npm registry.
- This release is prepared for npm publication but has not been published yet.
