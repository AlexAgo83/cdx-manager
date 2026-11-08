# Continue isolated runs — mission 4167c3a2e7

Fixes #122. Local Claude and Codex continuations reuse the parent's workspace,
network flag, mount permission and native conversation, including across chained
and detached runs. Model, effort, account and provider retain the existing pins.
Only transcript directories persist under `CDX_HOME/isolated-runs/`; neither the
host profile nor its configuration is mounted into the sandbox.

The conservative compatibility choice is to refuse old isolated runs without
retained transcript storage. `continue_run_workspace_gone` lets callers start a
fresh run after workspace/storage removal or replacement. Missing native
transcripts still return `continue_run_unavailable`. A changed cwd, permission,
or attempted network widening returns `continue_run_settings_mismatch`.
Remote continuation remains unsupported.

This extends the existing provider boundary decision in ADR 002. CLI regression
coverage uses both providers, read-only and writable workspace mounts, offline
and network-enabled settings, changed profile defaults, chained continuations,
and refusal before launch when boundary inputs change or storage disappears.
Fixtures use fake credentials and synthetic provider output; authenticated live
inference is not claimed. Timed local validation receipts are kept outside Git.
Complete green required GitHub CI on the merged commit is mandatory before merge.
