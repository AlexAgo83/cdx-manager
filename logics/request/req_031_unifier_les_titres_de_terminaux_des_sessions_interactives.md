## req_031_unifier_les_titres_de_terminaux_des_sessions_interactives - Unifier les titres de terminaux des sessions interactives
> From version: 0.16.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: interactive-session-ergonomics
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# Needs
- Identifier immédiatement, dans le titre de la fenêtre de terminal, la session cdx active et le dépôt ou dossier de travail.
- Obtenir la même convention de titre quel que soit le fournisseur Claude, Codex ou Antigravity.

# Context
- Claude reçoit déjà --name <session>, tandis que Codex affiche généralement le répertoire courant dans son TUI.
- Codex et Antigravity ne doivent pas dépendre d'un flag privé ou non documenté pour cette fonctionnalité.
- Les lancements interactifs sont construits dans src/provider_runtime.py et peuvent être enveloppés pour la capture de transcript.

# Acceptance criteria
- AC1: Un lancement interactif ou une reprise Claude via cdx affiche un titre au format session -- dossier.
- AC2: Un lancement interactif ou une reprise Codex via cdx affiche un titre au format session -- dossier.
- AC3: Un lancement interactif Antigravity via cdx affiche un titre au format session -- dossier.
- AC4: Le dossier affiché correspond au basename du cwd effectif du lancement, sans casser les lancements non interactifs, JSON, redirigés ou les transcripts.
- AC5: Les données session/cwd ne peuvent pas injecter de séquence de contrôle dans le titre du terminal.
- AC6: Les tests de lancement et les tests unitaires du runtime couvrent le format, les caractères de contrôle et les cas non-TTY.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_021_titres_de_terminal_coherents_pour_les_sessions_cdx`
- Architecture decision(s): (none yet)

# References
- User request: afficher session -- repo ou dossier pour Claude, Codex et Antigravity

# AI Context
- Summary: Unifier les titres de terminaux des sessions interactives
- Keywords: request-chain-scaffold, unifier les titres de terminaux des sessions interactives, development-ready
- Use when: You need to implement or review the scaffolded workflow for Unifier les titres de terminaux des sessions interactives.
- Skip when: The change is unrelated to this scaffolded request chain.

# Backlog
- `item_075_imposer_le_titre_session_dossier_aux_tui_interactifs`
