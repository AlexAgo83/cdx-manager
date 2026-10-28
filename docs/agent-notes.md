# Agent notes

Pitfalls and operator rules for any agent working in this repo (tracked here because AGENTS.md is local and ignored).

## Operator machine and test hosts (moved here from agent memory, 2026-10-28)
- Never run `pip` against cdx-manager on the operator's machines (install, update, uninstall, even a throwaway venv to test a published artifact): the operator manages the install. The README's `pip install -e` is for a dev checkout only. To verify a release, ask how it should be checked.
- Cross-platform checks run on Tower (`aagos@kdesktop`, Windows) and its WSL guest (`wsl.exe -d Ubuntu -u aagos -- ...`); an agent runs the scriptable part itself and only asks the operator to look at what appears on screen (notifications, windows). On Windows Tower the full pytest stops around 21% in `test_commands_runs_py` (`cdx run --detach` tests spawning real children): an environment quirk, not a regression; run single files or `-k` subsets synchronously and read GitHub CI for whole-suite Windows evidence. In cmd.exe `&` is a separator, Python buffers redirected stdout (use `-u`), and a killed SSH session leaves a truncated output that reads like a hang.
- In Tower's WSL the `codex` on PATH was the Windows npm install through interop (Windows-only native package); a Linux build lives at `~/.npm-global/bin/codex` (`npm i -g --prefix ~/.npm-global @openai/codex`): export that path first.
