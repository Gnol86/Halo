---
version: 1
slug: "frontend-src-halo-panel-ts"
primary_target: "frontend/src/halo-panel.ts"
related_targets: ["frontend/src/styles.ts","frontend/src/entity-picker.ts"]
---

# Panneau Halo

Mode: Operate. Surface: panneau Lit intégré à Home Assistant, administrateurs et habitants. Toutes les capacités actuelles restent accessibles. Choix utilisateur du 9 octobre 2026: pilotage d’abord, construction directe en code, organisation master-detail.

## Direction contract

THESIS: Une liste de pièces compacte reste visible pendant le pilotage et la configuration de la pièce choisie; les longs formulaires simultanés disparaissent.

OWN-WORLD: Le thème Home Assistant fournit les fonds, textes, accents, couleurs d’état, police, tailles, rayons, bordures et ombres; lotus et icônes monochromes natifs. Aucun univers chromatique Halo séparé.

STORY: Repérer une pièce et son état, agir immédiatement, puis ouvrir le groupe de réglages voulu. Le brouillon transversal et l’édition réelle restent distincts.

FIRST VIEWPORT: En-tête Halo compact et navigation globale; colonne des pièces avec recherche, état et commande; détail à droite avec nom, état, modes et commandes, puis sous-navigation et scènes. Sur mobile, liste puis détail avec retour explicite.

FORM: Pièces et panneau de détail, candidat structurel 4, seed 36e6496d; choisi par l’utilisateur sur la page de décision. Interaction signature: changer de pièce sans quitter le contexte de pilotage; aucun brouillon perdu. Révélations courtes, sans chorégraphie, mouvement réduit respecté. Profils édités un à un, transitions sous réglages. Tous les paramètres restent découvrables par leurs intitulés.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
