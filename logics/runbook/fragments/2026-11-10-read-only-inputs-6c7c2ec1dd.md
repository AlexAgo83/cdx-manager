# Read-only isolated inputs

Mission: `6c7c2ec1dd`.

Isolated runs accept repeatable `--ro-input NAME=PATH`. The execution host validates ownership, directory type and separation from the worktree, home configuration, cdx state and credential locations. Each directory is mounted read-only at `/opt/inputs/<lowercase name>`, with the matching provider environment variable pointing there. Internal symlinks are preserved without mounting their host targets.

Inputs are recorded in the run launch settings, forwarded to detached supervisors and worker payloads, and inherited by local continuations. Validation runs again before launch. An explicit continuation input list must match the parent's list. Remote continuations remain unavailable.

Conservative choices: reserve provider/cloud variable prefixes and credential-shaped variable names; protect hidden home entries and `.local` as configuration/credential containers, plus host runtime and known system credential locations. Worker inputs use absolute paths on the worker. No operator credentials or host measurements are required for this change.

Validation commands and measured results are recorded by the supplied mission test runner in the mission artifacts. Full green GitHub CI on the merged commit remains required before merge.

Final local results: `npm run lint` passed; `npm test` passed with 2,034 tests and five existing optional skips; `cargo test --manifest-path tray/Cargo.toml` passed all 99 tests; `npm pack --dry-run` and `uv build` passed. There is no separate typecheck script. All attempts, including failed initial checks and retries, used the supplied timer.

The initial environment inherited sandbox Git directory variables and an RTK database override, and lacked development tools and Cargo. Final Python checks used the locked development environment with `GIT_DIR`, `GIT_COMMON_DIR`, `GIT_WORK_TREE` and `RTK_DB_PATH` unset. Rust was installed in a mission-private temporary directory. A regression test caught a remote validation error being hidden behind the worker's generic setup diagnostic; the dedicated validation exit code now reports a fixed, credential-free error to the controller.
