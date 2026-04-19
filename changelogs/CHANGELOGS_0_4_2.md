# Changelog (`0.4.1 -> 0.4.2`)

Release date: 2026-04-19

## CDX Manager 0.4.2

CDX Manager 0.4.2 fixes Codex session bootstrap on Windows so `cdx add` can reuse an existing logged-in Codex CLI without requiring a second manual login flow. It also hardens executable resolution for the Codex probe so Windows shell shims and direct process spawning behave consistently.

### Codex auth bootstrap

- Seeded new Codex session auth homes from the global `~/.codex/auth.json` when available.
- Short-circuited the Codex auth probe when a session already has an auth file in its isolated home.
- Kept the per-session auth directory model intact after bootstrap so session isolation still applies.

### Windows command resolution

- Resolved `codex` through the active `PATH` before invoking the login-status probe.
- Applied the same command-resolution path to interactive provider launches when the default process spawner is used.
- Added regression coverage for Codex auth bootstrap and resolved-command spawning on Windows.

### Documentation

- Documented the Codex auth bootstrap behavior in the README.

### Validation

```bash
npm run lint
npm test
node bin/cdx.js rmv main --force
node bin/cdx.js add main
```
