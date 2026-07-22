# CDX Manager 0.11.1

## Highlights

- Added optional labels for saved sessions.
- Kept existing list and compact status output clean when no labels are present.
- Closed the session-label Logics corpus with full validation evidence.

## Changes

### Optional session labels

`cdx label <name> <label>` now attaches one short human-readable label to a saved session. Labels are stored as session metadata outside the `launch` dictionary, so they do not affect provider commands, auth checks, runtime state, ready/next selection, or launch history behavior.

`cdx label <name> --clear` removes the label and returns the session to the same shape as legacy unlabeled records.

The default `cdx` list and full `cdx status` table add a `LABEL` column only when at least one row has a label. Unlabeled rows render as `-`, and `cdx status --small` remains compact.

JSON outputs for `cdx --json`, `cdx status --json`, `cdx status <name> --json`, and `cdx label ... --json` expose label values for automation consumers.

Session copy, rename, export, and import preserve labels.

### Documentation and workflow

README and CLI help now document `cdx label <name> <label>` and `cdx label <name> --clear`.

The optional session-label Logics request, backlog item, product brief, and orchestration task are closed with validation evidence.

## Validation

- `python3 -m unittest discover -s test`
- `logics-manager flow validate req_012_add_optional_labels_to_cdx_sessions`
- `logics-manager status`
- `logics-manager health`
