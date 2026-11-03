# CDX Manager 0.25.9

Release date: 2026-11-03

This release expands isolated remote provider support and improves Antigravity
quota, usage reporting, and update feedback.

## Remote runs

- Integrate worker-owned Antigravity headless runs with mandatory isolation, a volatile home, restricted inference networking, and redacted output. Keep worker credentials on the worker and preserve local profile authentication. Live worker acceptance measurements remain required before claiming production support. (#98)
- Enable isolated remote Claude runs with a dedicated OAuth setup token stored on the controller and transported through stdin. Use a fresh memory-backed home per attempt, restrict inference traffic by default, and retain usage reporting and output redaction. (#95)
- Add remote Ollama text generation with an explicitly selected installed worker model through a restricted local relay. Limit requests to model inspection and non-streaming chat; keep the checkout read-only and report generated text and token usage. This mode does not edit repositories or act as an autonomous coding agent. (#94)

## Antigravity status and updates

- Show Antigravity quota, reset times, and reading age from a local statusLine integration that preserves existing commands. Record native headless token counters, and identify stale or expired quota readings. (#96)
- Keep successful `agy update` commands successful when no newer version can be verified. Report an `update_unverified` warning while retaining unknown latest-version status; non-zero updater exits still fail. (#93)

## Maintenance

- Record tray companion checksums for v0.25.8. (`d0c8d33b671234cf648da2b21b7bb0bfb0ce302e`)
- Record release archive checksums for v0.25.8. (`20fb80c7d115500c8da5be433526e195063258d9`)
