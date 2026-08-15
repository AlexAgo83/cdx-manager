## run_004_recovering_disk_space_from_cdx_profiles - Recovering disk space from CDX profiles
> Status: Draft
> Category: support
> Verified: 2026-08-15, reclaimed profile storage by moving unused Ollama models, caches, stale Claude Code extensions, and CDX session logs to the macOS Trash.
> Related request: (none yet)
> Related backlog: (none yet)
> Related task: (none yet)
> Reminder: Update status, category, verification, and linked refs when you edit this doc.

# Trigger
- `cdx disk` reports unexpectedly high usage.
- A CDX profile is large despite its conversation history being small.
- Disk space is needed and the profile or CDX process to clean is stopped.

# Prerequisites
- Run from the macOS user shell, not from inside the profile being cleaned.
- Close the target CDX/profile before moving its files.
- Keep the macOS Trash intact until the result has been verified.

# Procedure
1. Measure the global CDX store and identify large profiles:

   ```sh
   cdx disk
   du -sh "$HOME/.cdx/profiles"/* | sort -h
   ```

   `cdx disk` measures `~/.cdx`; Codex conversation history is separate at
   `~/.codex/sessions`.

2. Inspect a Claude-backed profile before changing it:

   ```sh
   PROFILE=claw
   PROFILE_HOME="$HOME/.cdx/profiles/$PROFILE/claude-home"
   du -sh "$PROFILE_HOME"/* "$PROFILE_HOME"/.[!.]* 2>/dev/null | sort -h
   ```

   Usual low-risk candidates are `.cache`, `Library/Caches`, old
   `anthropic.claude-code-*` directories under `.vscode/extensions`, and an
   unused `.ollama/models` directory. Preserve the newest extension and do
   not remove a model that is still needed.

3. Move candidates to a named Trash folder rather than deleting them:

   ```sh
   TRASH_DIR="$HOME/.Trash/cdx-profile-cleanup-$(date +%Y%m%d)"
   mkdir -p "$TRASH_DIR"
   for path in "$PROFILE_HOME/.cache" "$PROFILE_HOME/Library/Caches"; do
     [ -e "$path" ] && mv "$path" "$TRASH_DIR/"
   done
   ```

   Move stale extensions individually after listing them; retain the highest
   version. For an unused Ollama model, prefer `ollama rm <model>` while using
   the matching profile's Ollama store. If the service is unavailable, move
   the verified model directory or blobs to the Trash as one recoverable unit.

4. For native Codex profiles, session diagnostics can dominate storage while
   the actual sessions remain smaller. Move completed `log/cdx-session-*.log`
   files to a separate Trash folder; do not touch `sessions/` unless
   intentionally pruning conversation history.

# Verification
- Re-run `cdx disk` and the `du` commands above; the profile should shrink.
- Start the profile and confirm its retained extension/tooling still works.
- Empty the macOS Trash only after that check. Moving files out of `.cdx`
  lowers `cdx disk` immediately, but macOS disk space is released only when
  the Trash is emptied.

# Rollback
- Move the needed directory from the named Trash folder back to its original
  profile path. Reinstall an extension or pull an Ollama model if it was
  intentionally discarded after verification.

# References
- Related request: (none yet)
- Related backlog: (none yet)
- Related task: (none yet)
- `run_002_finding_out_which_cdx_and_which_home_you_are_talking_to`
