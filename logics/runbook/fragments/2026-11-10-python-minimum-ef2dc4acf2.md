# Python 3.10 minimum — mission ef2dc4acf2

Python 3.10 or newer is now required for the next patch release. Python 3.9
reached end of life in October 2025; its development dependency branch kept
pytest 8.4.2 and Dependabot alert #2 open. The development extra now requires
pytest >=9.0.3 unconditionally, and `uv lock` retains pytest 9.2.0 while removing
packages and resolution branches needed only by Python 3.9. No unrelated
package upgrade is requested.

Update package metadata, README, installation guidance, the npm interpreter
probe, CI and the unreleased changelog. Historical audit records and comments
about past Python 3.9 observations remain historical evidence. The standalone
installers do not contain interpreter version probes. Keep existing runtime
code unchanged. Ruff targets Python 3.10; defer the newly enabled B905 rule to
preserve the previous lint policy without editing existing zip calls.

Validation uses the supplied mission timer. Install the development extra with
`uv sync --locked --extra dev`; the prepared frozen environment lacked pytest.
Unset inherited `GIT_DIR`, `GIT_COMMON_DIR`, `GIT_WORK_TREE` and `RTK_DB_PATH`
for Python tests so temporary repository and RTK fixtures use their own state.
For uv-managed Python 3.10, set `PYTHONHOME` to its installation root so the
existing fixture that copies the interpreter under a provider name can find
its standard library. This is a local validation environment setting.
Validate the full Python suite on the new minimum version, lint, tray tests,
lock consistency, Python distributions and the npm package dry-run. Exact
commands, outcomes and timings are stored in the external mission receipts.
All required GitHub CI checks on the merged commit must still pass before merge;
local Linux validation does not establish Windows or macOS results.
