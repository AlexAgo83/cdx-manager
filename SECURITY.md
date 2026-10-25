# Security Policy

## Supported Versions

Security fixes target the latest published release. Upgrade with `cdx update`
(or your package manager) before testing or reporting, unless the issue is about
the upgrade path itself.

## Reporting a Vulnerability

Please do not open public issues for suspected vulnerabilities.

Report privately through GitHub:

https://github.com/AlexAgo83/cdx-manager/security/advisories/new

Include:

- cdx version (`cdx --version`) and how it was installed (npm, pipx, uv, PyPI,
  or source);
- operating system, Python and Node versions, and the provider involved
  (Claude, Codex, Antigravity, Ollama);
- reproduction steps with the smallest safe example;
- the expected impact: credential exposure, another profile's data, a
  network-reachable surface, or a tampered download.

Do not include real tokens, API keys, `auth.json` or credential files, export
bundles, or transcripts with private content. Redact them, or describe their
shape instead.

## Response Expectations

The maintainer will triage the report, confirm affected versions, and
coordinate a fix before public disclosure when appropriate. Fixes ship through
the normal GitHub Release, npm and PyPI pipeline.

## Security Scope

cdx runs locally and manages provider credentials for several accounts. The
sensitive surfaces are:

- **Profile isolation.** Each session runs with its own HOME (`~/.cdx/profiles/<name>`).
  A launch that reads or writes another profile's credentials, memory or
  transcripts is in scope.
- **Credentials.** Claude setup-tokens and OAuth files, Codex `auth.json`, and
  what cdx passes to a provider's environment. `cdx set <name> --scrub-env on`
  keeps credentials away from the commands, hooks and MCP servers a Claude agent
  starts; a leak despite it is in scope.
- **Export bundles.** `cdx export --include-auth` encrypts credentials with a
  passphrase. Weak key derivation, plaintext leftovers or an import that trusts
  a tampered bundle are in scope.
- **The viewer.** `cdx view --lan` and `--lan-rw` expose a browser viewer on the
  network. Expose it only to networks you trust; prefer a Tailscale or WireGuard
  tunnel to public exposure.
- **Downloads and scheduled jobs.** `cdx tray install` downloads the companion
  and verifies its published checksum; agent alerts and `cdx ready` install
  hooks and LaunchAgents or scheduled tasks. A bypassed checksum, or a hook or
  job that runs something other than cdx, is in scope.

Out of scope: vulnerabilities in the providers themselves (Claude Code, Codex,
Antigravity, Ollama), and actions an agent takes with permissions you granted it
(`--permission full`).
