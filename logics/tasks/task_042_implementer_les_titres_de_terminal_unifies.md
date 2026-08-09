## task_042_implementer_les_titres_de_terminal_unifies - Implémenter les titres de terminal unifiés
> From version: 0.16.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Lire le contexte et vérifier les invariants du runtime de lancement, notamment le wrapper script et les chemins launch/resume.
- [x] 2. Ajouter le helper de titre assaini et le garde-fou TTY au niveau partagé de provider_runtime.
- [x] 3. Brancher le cycle de vie du titre autour du processus interactif avec arrêt garanti.
- [x] 4. Écrire les tests ciblés, documenter la convention puis exécuter lint et les suites Python runtime/launch.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_075_imposer_le_titre_session_dossier_aux_tui_interactifs`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_075`. Proof: `_start_terminal_title` runs for Claude launch and resume in `src/provider_runtime.py`; `StartTerminalTitleTests.test_launch_and_resume_on_a_tty_hold_the_title`.
- request-AC2 -> `item_075`. Proof: Codex reaches the same runtime path with no provider flag added; `StartTerminalTitleTests.test_every_supported_provider_uses_the_same_runtime_path`.
- request-AC3 -> `item_075`. Proof: Antigravity is in `TERMINAL_TITLE_PROVIDERS` and covered by the same test.
- request-AC4 -> `item_075`. Proof: `format_terminal_title` uses `basename(abspath(cwd or getcwd()))`; JSON launches pass `title_enabled=False` from `src/commands/launch.py`, headless and non-TTY paths never start a keeper. `TerminalTitleFormatTests.test_folder_is_basename_of_effective_cwd`, `test_non_tty_stream_writes_nothing`, `test_disabled_json_run_writes_nothing`.
- request-AC5 -> `item_075`. Proof: `_sanitize_terminal_title_component` strips ESC and the C0/C1 ranges; `TerminalTitleFormatTests.test_control_characters_are_stripped`.
- request-AC6 -> `item_075`. Proof: 15 new tests in `test/test_provider_runtime_helpers_py.py` plus `test_interactive_launch_holds_the_title_and_releases_it_on_failure` in `test/test_runtime_py.py`.

# Validation
- `python3 -m pytest`: 693 passed, 1 pre-existing failure unrelated to this slice (`test_send_desktop_notification_dispatches_to_macos_osascript`, fails identically on the unmodified tree).
- `ruff check .`: all checks passed.
- `logics-manager lint`: OK. `logics-manager audit`: OK (only the deferred-traceability warnings this closeout resolves).

# Report
- The title lives in the shared interactive runtime (`_run_interactive_provider_command_impl`), so Claude, Codex and Antigravity get it without any change to their launch arguments or transcript capture.
- A single write at launch does not survive: provider TUIs repaint their own title. `_TerminalTitleKeeper` re-emits the OSC sequence every 5s on a daemon thread and is stopped in a `finally`, so the success, error and signal paths all release it.
- Guards are deliberately layered - action must be launch/resume, provider must not be Ollama, stdout must be a TTY, and `--json` launches opt out explicitly - because each rules out a different way the sequence could reach something that is not a terminal.
- The separator is an em dash (` — `), chosen by the operator over the ASCII `--` the request text spelled it with. A terminal whose stdout encoding cannot represent it makes the write raise, which the best-effort `_write` swallows: no title rather than a crash.

# AI Context
- Summary: Implémenter les titres de terminal unifiés
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_031_unifier_les_titres_de_terminaux_des_sessions_interactives`
- Product brief(s): `prod_021_titres_de_terminal_coherents_pour_les_sessions_cdx`
- Architecture decision(s): (none yet)
