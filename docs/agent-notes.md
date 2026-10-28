# Agent notes

Pitfalls and operator rules for any agent working in this repo (tracked here because AGENTS.md is local and ignored).

## Operator machine and test hosts (moved here from agent memory, 2026-10-28)
- Never run `pip` against cdx-manager on the operator's machines (install, update, uninstall, even a throwaway venv to test a published artifact): the operator manages the install. The README's `pip install -e` is for a dev checkout only. To verify a release, ask how it should be checked.
- Cross-platform checks run on Tower (`aagos@kdesktop`, Windows) and its WSL guest (`wsl.exe -d Ubuntu -u aagos -- ...`); an agent runs the scriptable part itself and only asks the operator to look at what appears on screen (notifications, windows). On Windows Tower the full pytest stops around 21% in `test_commands_runs_py` (`cdx run --detach` tests spawning real children): an environment quirk, not a regression; run single files or `-k` subsets synchronously and read GitHub CI for whole-suite Windows evidence. In cmd.exe `&` is a separator, Python buffers redirected stdout (use `-u`), and a killed SSH session leaves a truncated output that reads like a hang.
- In Tower's WSL the `codex` on PATH was the Windows npm install through interop (Windows-only native package); a Linux build lives at `~/.npm-global/bin/codex` (`npm i -g --prefix ~/.npm-global @openai/codex`): export that path first.

## Releases and Tower installs (moved here from Codex memory, 2026-10-28)
- A pushed `main` or a source-checkout deploy is not a release. Call a release ready only once the CI and CodeQL runs for the exact pushed SHA are green, the tag's assets and `release-archives.json` checksums are published, npm and PyPI both serve the version, and `logics-manager release validate <version>` passes. Delete a stale `dist/` before building: old artifacts make `twine check` pass on the wrong files.
- Python tests live in `test/` (not `tests/`).
- On Tower, `make install` can fail with `EACCES` on `/usr/local/lib/node_modules`: install the tagged release with the checksum-verified user-scoped `install.sh` instead. On a source-linked install, `cdx update --yes --version <tag>` only switches the checkout. Tower's daily `auto-update` job (`cdx update all --yes --json`) can finish without every provider converging: check the installed versions afterwards.
