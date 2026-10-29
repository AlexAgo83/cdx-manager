# CDX Manager 0.24.4

Release date: 2026-10-29

This patch adds explicit recovery of missing serving models in existing run history, using evidence tied to each run. (#59)

## History and statistics

- Add `cdx history backfill-models`, with a read-only preview by default and `--dry-run`, `--apply`, and `--json` options. Recover models from preserved run output, matching run reports, or exact Codex and Claude conversation transcripts. (#59)
- Keep missing or ambiguous evidence unknown rather than guessing from configured models or the latest conversation. Preserve existing models and token counts; report recovery counts, unknown reasons, and samples. (#59)
- With `--apply`, back up the original history and replace it atomically under the history lock. Repeated runs leave recovered rows alone. Subsequent statistics can price recovered models when the local price table recognizes them. (#59)

## Maintenance

- Record tray companion checksums for v0.24.3. (`bae6f34b733c91ef44070d25bb86015fa31f71ca`)
- Record release archive checksums for v0.24.3. (`8a1d4938a11f83cbe2eb8abc324a55b909f72837`)
