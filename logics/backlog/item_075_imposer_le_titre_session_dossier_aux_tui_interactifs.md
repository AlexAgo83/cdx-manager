## item_075_imposer_le_titre_session_dossier_aux_tui_interactifs - Imposer le titre session -- dossier aux TUI interactifs
> From version: 0.16.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: interactive-session-ergonomics
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- Chaque fournisseur contrôle actuellement son titre de fenêtre selon ses propres conventions.
- Un simple titre écrit avant le lancement peut être remplacé par le TUI du fournisseur.

# Scope
- In:
  - Ajouter au runtime interactif une petite abstraction qui construit session -- basename(cwd).
  - Assainir les caractères de contrôle dans le nom de session et le dossier avant toute émission OSC.
  - Démarrer un maintien du titre seulement pour launch/resume interactifs lorsque stdout est un TTY, et l'arrêter systématiquement à la fin ou sur erreur.
  - Couvrir Claude, Codex et Antigravity via le chemin runtime partagé; ne pas changer les arguments natifs des fournisseurs.
  - Ajouter des tests unitaires ciblés et documenter la convention dans README.
- Out:
  - Forcer des options non documentées de Claude, Codex ou agy.
  - Affecter cdx run, les exécutions détachées, les flux JSON ou les sorties redirigées.
  - Enregistrer ou restaurer le titre antérieur du terminal.

# Acceptance criteria
- AC1: Le helper de titre produit exactement session -- dossier à partir de la session et du cwd, et supprime ESC ainsi que les contrôles C0/C1 pertinents.
- AC2: Le maintien du titre n'est activé que pour launch/resume sur stdout TTY; il ne produit rien pour les contextes non-TTY, JSON et tests capturés.
- AC3: Le mécanisme reste actif pendant l'exécution du fournisseur afin de reprendre la main si son TUI modifie le titre, puis s'arrête dans le bloc finally.
- AC4: Les mêmes appels runtime couvrent Claude, Codex et Antigravity sans modifier leurs arguments de lancement ni la capture de transcript.
- AC5: Les suites runtime et launch existantes passent, avec de nouveaux tests pour le format, l'assainissement et le garde-fou non-TTY.
- AC6: README décrit le format session -- dossier et les fournisseurs concernés.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: Le helper de titre produit exactement session -- dossier à partir de la session et du cwd, et supprime ESC ainsi que les contrôles C0/C1 pertinents.
- request-AC2 -> This backlog slice. Proof: AC2: Le maintien du titre n'est activé que pour launch/resume sur stdout TTY; il ne produit rien pour les contextes non-TTY, JSON et tests capturés.
- request-AC3 -> This backlog slice. Proof: AC3: Le mécanisme reste actif pendant l'exécution du fournisseur afin de reprendre la main si son TUI modifie le titre, puis s'arrête dans le bloc finally.
- request-AC4 -> This backlog slice. Proof: AC4: Les mêmes appels runtime couvrent Claude, Codex et Antigravity sans modifier leurs arguments de lancement ni la capture de transcript.
- request-AC5 -> This backlog slice. Proof: AC5: Les suites runtime et launch existantes passent, avec de nouveaux tests pour le format, l'assainissement et le garde-fou non-TTY.
- request-AC6 -> This backlog slice. Proof: AC6: README décrit le format session -- dossier et les fournisseurs concernés.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_021_titres_de_terminal_coherents_pour_les_sessions_cdx`
- Architecture decision(s): (none yet)
- Request: `req_031_unifier_les_titres_de_terminaux_des_sessions_interactives`
- Primary task(s): `task_042_implementer_les_titres_de_terminal_unifies`

# AI Context
- Summary: Imposer le titre session -- dossier aux TUI interactifs
- Keywords: scaffolded-backlog, imposer le titre session -- dossier aux tui interactifs, implementation-ready
- Use when: Implementing the scaffolded slice for Imposer le titre session -- dossier aux TUI interactifs.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
