# Truthful workstation update inventory (mission 67f3d8f974)

The supplied checkout is cdx-manager, not example-project. Neither
`scripts/auto-update.py` nor `macos-auto-update.zsh` is present. Keep their
existing JSON consumption compatible: `installed`, `version`, `latest_version`,
`update_command`, `up_to_date`, `not_installed`, and `update_available` remain;
`unknown` and an optional `reason` now expose missing evidence. A successful
command exit does not certify that every installed tool is current.

The assertion and its reasoning live together in `src/update_all.py` and
`test/test_update_all_py.py`: only identical known versions establish currency.
This mission records the operating context in this fragment as requested,
without adding history to shared runbooks or design documents.

## Conservative assumptions

- The existing `agy` executable denotes the original Antigravity editor. Its
  vendor releases feed is distinct from Antigravity Hub and IDE 2; never compare
  versions across those products. No other Antigravity binary is guessed.
- Latest release checks are read-only, use a five-second timeout, and return
  unknown after failures or invalid data. Ollama uses its vendor update API,
  with OS/architecture and baseline version 0.0.0, extracting the version from
  the returned artifact URL as the vendor updater does. Local server version
  endpoints cannot establish the latest published version.
- An advertised CLI update command or a resolved Homebrew installation is
  required for automatic updates. Missing native commands require manual vendor
  action; no install script, package name, or elevation is invented.
- JSON with `--yes` retains the pre-update plan and separate action results.

## Verification

All local validation attempts are measured by
`.mission-input/mission-test-runner.py`; receipts are in
`.mission-artifacts/mission-tests.jsonl`. Initial lint found a missing development
ruff dependency; `uv sync --frozen --extra dev` restored it. A subsequent lint
found an unbound loop variable in a new test, corrected before final validation.
Faked source tests cover matching versions, outdated versions, unavailable or
malformed sources, absent tools, native application, JSON/text uncertainty,
Ollama client version selection, and verified Homebrew paths.

No release, commit, push, PR, or host mutation is performed. Host inventories
and the external example-project callers are not available here. Review the original
Antigravity product assumption and external callers' handling of `unknown`;
no real Host C measurement is claimed from fixtures.

Read-only public source probes on 2026-11-02 returned Claude 2.1.316, RTK 1.1.0,
and original Antigravity 2.0.0. Ollama's update API returned HTTP 204 with no
version for Linux/amd64 baseline 0.0.0: the plan correctly leaves that source
unknown. The same API returned a versioned artifact URL on macOS/Windows; do
not substitute another platform's release for a missing local-platform result.
These are public source observations, not installed-host measurements.

Final validation passed: `npm run lint`; `npm test` (1,407 tests);
`cargo test --manifest-path tray/Cargo.toml` (99 tests); `npm pack --dry-run`;
`uv build --wheel --out-dir /tmp/cdx-mission-67f3d8f974-dist`;
`logics-manager lint --require-status`; and
`logics-manager audit --group-by-doc` (zero blocking issues, six existing
warnings). The targeted maintenance/update suite also passed. No separate
project typecheck command exists; lint includes Python compilation.
