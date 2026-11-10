# Canonical isolated-run test paths — mission 77b6e502a9

PR #128's isolated-run refusal fixture stored raw temporary paths, although real
isolated launches persist canonical paths for both the checkout and conversation
storage. macOS temporary paths can traverse `/var` to `/private/var`; Windows
canonicalization can change path casing. The fixture therefore hit the missing
workspace guard before the intended settings-mismatch or expired-session guard.

Resolve both fixture paths before recording the parent run, canonicalize the
source-project fixture root, and compare the sandbox checkout with the canonical
requested directory. Keep production guards unchanged. Explicit workspace and storage aliases containing `..` must still be
refused. This is a local fixture correction under ADR 030, with no product or
architecture rule change and no new workflow chain.

Validation includes the run-command tests with an ordinary temporary root and a
symlinked temporary root, full Python tests, lint, tray tests and package builds.
Exact commands, exit codes and timings live in the external mission receipts.
Run Python test commands with inherited `GIT_DIR`, `GIT_WORK_TREE`,
`GIT_COMMON_DIR` and `RTK_DB_PATH` unset: otherwise temporary Git fixtures
incorrectly address the read-only mission repository, and RTK fixtures inherit
the sandbox database instead of their own histories.

The supplied CodeQL initialization failure was an HTTP 504 downloading the
CodeQL CLI, before source analysis. No workflow change is justified by this
transient download failure. Host A must rerun CodeQL and all required GitHub CI
checks on the prepared commit. Local Linux results do not replace macOS or
Windows CI, and no successful remote rerun is claimed here.
