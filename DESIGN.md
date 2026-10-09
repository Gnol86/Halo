---
name: "Halo"
description: "Panneau Home Assistant compact pour piloter les lumières et retrouver tous leurs réglages."
colors:
  background: "var(--primary-background-color, Canvas)"
  surface: "var(--ha-card-background, var(--card-background-color, var(--primary-background-color, Canvas)))"
  muted-background: "var(--secondary-background-color, var(--ha-card-background, var(--card-background-color, var(--primary-background-color, Canvas))))"
  primary-text: "var(--primary-text-color, CanvasText)"
  secondary-text: "var(--secondary-text-color, var(--primary-text-color, CanvasText))"
  divider: "var(--divider-color, var(--outline-color, GrayText))"
  accent: "var(--primary-color, Highlight)"
  on-accent: "var(--text-primary-color, HighlightText)"
  selected: "color-mix(in srgb, var(--primary-color, Highlight) 10%, var(--ha-card-background, var(--card-background-color, var(--primary-background-color, Canvas))))"
  light-on: "var(--state-light-on-color, var(--state-light-active-color, var(--state-active-color, var(--primary-color, Highlight))))"
  light-off: "var(--state-light-off-color, var(--state-light-inactive-color, var(--state-inactive-color, var(--secondary-text-color, var(--primary-text-color, CanvasText)))))"
  error: "var(--error-color, var(--primary-text-color, CanvasText))"
  disabled-text: "var(--disabled-text-color, var(--secondary-text-color, var(--primary-text-color, CanvasText)))"
  header-background: "var(--app-header-background-color, var(--ha-card-background, var(--card-background-color, var(--primary-background-color, Canvas))))"
  header-text: "var(--app-header-text-color, var(--primary-text-color, CanvasText))"
  input-background: "var(--input-fill-color, var(--ha-card-background, var(--card-background-color, var(--primary-background-color, Canvas))))"
  input-text: "var(--input-ink-color, var(--primary-text-color, CanvasText))"
  input-border: "var(--input-outlined-idle-border-color, var(--divider-color, var(--outline-color, GrayText)))"
typography:
  room-title:
    fontFamily: "var(--ha-font-family-heading, var(--ha-font-family-body, inherit))"
    fontSize: "var(--ha-font-size-2xl, 24px)"
    fontWeight: "var(--ha-font-weight-bold, 700)"
    lineHeight: "var(--ha-line-height-condensed, 1.2)"
  headline:
    fontFamily: "var(--ha-font-family-heading, var(--ha-font-family-body, inherit))"
    fontSize: "var(--ha-font-size-xl, 20px)"
    fontWeight: "var(--ha-font-weight-bold, 700)"
    lineHeight: "var(--ha-line-height-condensed, 1.2)"
  title:
    fontFamily: "var(--ha-font-family-heading, var(--ha-font-family-body, inherit))"
    fontSize: "var(--ha-font-size-l, 16px)"
    fontWeight: "var(--ha-font-weight-bold, 700)"
    lineHeight: "var(--ha-line-height-condensed, 1.2)"
  body:
    fontFamily: "var(--ha-font-family-body, var(--paper-font-body1_-_font-family, inherit))"
    fontSize: "var(--ha-font-size-m, 14px)"
    fontWeight: "var(--ha-font-weight-normal, 400)"
    lineHeight: "var(--ha-line-height-normal, 1.6)"
  label:
    fontFamily: "var(--ha-font-family-body, var(--paper-font-body1_-_font-family, inherit))"
    fontSize: "var(--ha-font-size-s, 12px)"
rounded:
  control: "var(--ha-border-radius-md, 8px)"
spacing:
  ha-2: "var(--ha-space-2, 8px)"
  ha-3: "var(--ha-space-3, 12px)"
  ha-4: "var(--ha-space-4, 16px)"
  ha-5: "var(--ha-space-5, 20px)"
  ha-6: "var(--ha-space-6, 24px)"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-accent}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "7px 12px"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.primary-text}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "7px 12px"
  button-icon:
    backgroundColor: "transparent"
    textColor: "{colors.primary-text}"
    rounded: "{rounded.control}"
    padding: "7px"
    size: "36px"
  input:
    backgroundColor: "{colors.input-background}"
    textColor: "{colors.input-text}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "7px 10px"
  global-nav:
    backgroundColor: "transparent"
    textColor: "{colors.header-text}"
    padding: "var(--ha-space-3, 12px) var(--ha-space-4, 16px)"
  room-tab-selected:
    backgroundColor: "{colors.selected}"
    textColor: "{colors.accent}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
  status:
    textColor: "{colors.secondary-text}"
    typography: "{typography.label}"
    padding: "2px 0"
  condition:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.primary-text}"
    rounded: "{rounded.control}"
    padding: "12px"
  room-list-item-selected:
    backgroundColor: "{colors.selected}"
    rounded: "{rounded.control}"
    padding: "3px"
  savebar:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.primary-text}"
    padding: "12px 20px calc(12px + env(safe-area-inset-bottom, 0px))"
---

# Design System: Halo

Dernière mise à jour : **9 octobre 2026**.

## Overview

**Creative North Star: "Le panneau de pilotage Home Assistant"**

Halo est un panneau de pilotage domestique compact, intégré visuellement à Home Assistant. Il permet de lire l’état réel d’une pièce, de commander ses lumières puis d’ouvrir le groupe de réglages voulu. Les couleurs, la typographie et les propriétés des contrôles suivent le thème actif, avec des replis lorsque Home Assistant ne fournit pas une variable.

La refonte du 9 octobre 2026 est **actée et implémentée** : pilotage prioritaire, liste et détail des pièces, réglages en sous-vues et profils édités un à un. Elle remplace l’ancienne direction esthétique laissée ouverte et les longs formulaires simultanés. La densité vient de l’organisation et de la divulgation progressive, sans retrait d’option métier.

**Key Characteristics:**

- Pilotage accessible avant la configuration.
- Thème Home Assistant vivant, sans palette Halo indépendante.
- Listes, séparateurs et aides dépliables pour une lecture compacte.
- Brouillon transversal préservé et édition réelle explicitement distincte.

Ce document est la référence des règles visuelles, d’organisation et d’interaction du dashboard, maintenue en temps réel selon [AGENTS.md](AGENTS.md). Les fonctionnalités métier restent définies dans [PROJET.md](PROJET.md), l’état disponible dans [README.md](README.md), le contexte produit dans [PRODUCT.md](PRODUCT.md) et la direction de cette surface dans [le contrat du panneau](.impeccable/surfaces/frontend-src-halo-panel-ts.md). Le frontmatter contient les tokens normatifs extraits de [styles.ts](frontend/src/styles.ts) et [entity-picker.ts](frontend/src/entity-picker.ts) ; les propriétés hors de son schéma et les composants autonomes figurent dans [.impeccable/design.json](.impeccable/design.json).

### Statut et vérifications

La refonte est implémentée dans le panneau fonctionnel, avec son bundle reconstruit. Les vérifications de cette tâche comprennent **219 tests Python**, **52 tests frontend** (43 du panneau et 9 du modèle), les contrôles TypeScript et Ruff et la construction du bundle. Les aperçus ont été examinés à **390 et 1 436 pixels** de large, en clair, sombre et avec un thème personnalisé et une police à **125 %**. Ces aperçus utilisent des données simulées.

Des parcours ciblés ont aussi été vérifiés dans **Home Assistant 2026.10.0 isolé avec des lampes simulées** : scène partielle, ouverture de la fenêtre native d’une lampe avec l’effet « Candle », annulation libérant la session, import de deux lampes retenues/deux entités ignorées jusqu’au brouillon puis à son abandon. Les limites et preuves détaillées se trouvent dans [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md). Ces essais ne prouvent pas tous les parcours dans Home Assistant, le comportement des lampes du logement, un push ou un déploiement domestique.

### Identité existante

- **Nom :** Halo.
- **Symbole demandé :** une fleur de lotus.
- **Ressources disponibles :** icônes transparentes de 256 et 512 pixels dans `custom_components/halo/brand/`.
- **Source et prompt :** [assets/branding/README.md](assets/branding/README.md).

Le README référence le lotus par une URL absolue GitHub pour permettre son affichage dans la présentation HACS. La liste de HACS 2.0.5 utilise un mécanisme distinct qui ne prend pas encore en charge les icônes embarquées ; ce défaut d’affichage ne remet pas en cause les ressources graphiques. Voir le [diagnostic HACS](docs/HACS.md#affichage-du-lotus).

L’image de marque actuelle emploie des tons chauds. Ces couleurs ne constituent pas, à elles seules, une palette validée pour le dashboard. La barre latérale Home Assistant et l’en-tête Halo utilisent le lotus monochrome natif **`mdi:spa`**, dont la couleur suit le thème et l’état de sélection, comme les autres icônes. Le nom `mdi:flower-lotus`, qui ne désigne pas une icône valide, est remplacé. [Lotus du catalogue Material Design Icons](https://pictogrammers.com/library/mdi/icon/spa/).

Le bouton « Ouvrir le menu Home Assistant » ajouté par Halo est supprimé de son en-tête, à la demande du 9 octobre 2026. L’en-tête conserve le lotus et le nom Halo ; le descriptif est masqué dans la refonte compacte et le menu de l’application hôte n’est pas modifié.

## Colors

La couleur appartient au thème Home Assistant. Les tokens conservent les expressions CSS et leurs replis ; aucune couleur fixe ni rampe chromatique indépendante n’est déduite des images de marque.

### Primary

- **Accent de Home Assistant** : action principale, focus, sélection, courbes et icônes de navigation sélectionnées.
- **Texte sur accent** : libellé du bouton principal et sélection de texte.
- **Sélection teintée** : mélange léger de l’accent et de la surface, employé pour la pièce, le profil ou l’onglet courant et les messages informatifs.

### Neutral

- **Fond du panneau, surface et fond secondaire** : distinguent la zone de détail, la liste et les contrôles au repos ou au survol.
- **Texte principal et secondaire** : séparent les libellés d’action des aides, identifiants, métadonnées et statuts.
- **Séparateur** : structure les listes, groupes et limites de panneaux sans multiplier les cartes.
- **En-tête et champs** : reprennent aussi leurs variables dédiées Home Assistant, en priorité sur les rôles généraux.

### États

Les couleurs allumé/éteint proviennent des variables d’état des lumières, avec les replis d’état généraux puis les rôles du panneau. Erreur et désactivation reprennent leurs variables Home Assistant. La couleur accompagne un nom, un état textuel ou un attribut accessible ; elle ne suffit pas à expliquer une indisponibilité ou une pause.

**The Thème hôte Rule.** Le thème Home Assistant est la source des couleurs, y compris les états, les champs et l’en-tête. Les replis CSS gardent le panneau lisible lorsque certaines variables manquent ; ils ne définissent pas une palette Halo.

## Typography

**Police des titres :** famille de titres Home Assistant, puis famille de corps et héritage.
**Police de corps :** famille de corps Home Assistant, puis ancienne variable de corps et héritage.

La hiérarchie reste courte et fonctionnelle. Il n’existe pas de police d’affichage propre à Halo. Les tailles et graisses du frontmatter sont des références dynamiques au thème ; les valeurs de repli ne sont pas des dimensions imposées à tous les thèmes.

### Hiérarchie

- **Titre de pièce** : repère principal du détail ; il reprend la taille de titre de page sur mobile.
- **Titre de page** : pages globales et nom Halo dans l’en-tête sur grand écran.
- **Titre de section** : groupes de réglages, liste de pièces et courbes.
- **Corps** : champs, commandes, texte d’aide courant.
- **Libellé secondaire** : métadonnées, états, compteurs et aides compactes. Les compteurs et valeurs graphiques utilisent des chiffres tabulaires.

Les aides longues sont limitées à une largeur de lecture de (75ch), les explications d’état vide à (65ch). Les noms personnalisés et identifiants longs reviennent à la ligne. Les contrôles reprennent la police du panneau et le sélecteur d’entités hérite de ce même contexte.

**The Typographie hôte Rule.** Les titres et le texte suivent les familles et les tailles Home Assistant. Ne pas ajouter de police décorative ni une hiérarchie d’affiche à ce panneau de pilotage.

### Langues et textes

**Statut : implémenté et testé localement.** Les catalogues anglais et français du panneau et les traductions natives de l’intégration sont présents.

- **L’anglais est la langue de référence.** Tous les textes Halo disposent également d’une traduction française.
- Le panneau suit la langue effective de l’interface Home Assistant de l’utilisateur : français pour `fr` et ses variantes, anglais pour les autres langues.
- Les traductions de l’intégration suivent les mécanismes natifs de Home Assistant.
- Les noms personnalisés de pièces, de profils et de scènes restent inchangés.
- Les identifiants techniques restent indépendants de la langue ; les catalogues doivent permettre l’ajout ultérieur de langues.

La langue de chaque utilisateur est respectée : le panneau n’impose pas une langue unique au logement. Les textes actuels privilégient des intitulés directs et des aides dépliables ; un glossaire éditorial complet reste à définir. Les libellés français de ce document décrivent les contrôles, sans remplacer l’anglais comme langue produit de référence.

## Layout

Le cadre occupe la hauteur disponible du panneau. L’en-tête et la barre de sauvegarde restent dans ce cadre ; le contenu intermédiaire défile. La barre est ainsi persistante au bas de la fenêtre sans superposition aux derniers champs. Ce comportement est obtenu par la disposition flex, pas par une surcouche `position: fixed`.

### Navigation globale et disposition adaptative

- Trois entrées : **Pièces**, **Profils de lumière naturelle** et **Réglages globaux** ; les deux dernières sont réservées aux administrateurs.
- Sur grand écran, la colonne des pièces (264px) reste visible à gauche du détail ; elle passe à (224px) jusqu’au seuil intermédiaire (1100px). Elle contient recherche, nombre de pièces, nom, état, nombre de lumières et commande rapide. Sur tous les écrans, les pièces configurées dans le brouillon courant précèdent les autres, avec l’ordre fourni par Home Assistant préservé dans chaque catégorie, y compris pendant la recherche.
- À (760px) et en dessous, les pièces passent à une liste puis un détail avec retour explicite. Les onglets de pièce défilent horizontalement si nécessaire. Le détail ne juxtapose plus la liste à son contenu.
- Les profils ont une liste (240px) et un seul éditeur affiché. Sur petit écran, la liste précède l’éditeur dans le même défilement ; elle ne devient pas une seconde pile d’éditeurs.
- Les réglages globaux, l’éditeur de scène et l’import limitent leur contenu à (980px). Les grilles de courbes et de champs s’adaptent à leur largeur disponible.

Les espacements réutilisés suivent les variables Home Assistant du frontmatter. Les adaptations compactes, rangées et grilles conservent aussi des valeurs structurelles locales : ces mesures ne constituent pas une nouvelle échelle globale. Les cibles passent au minimum à (44px) avec un pointeur tactile ; les cases à cocher conservent leur propre dimension. L’en-tête se replie et la barre de sauvegarde passe sur deux colonnes d’actions sur mobile, en préservant la zone sûre inférieure.

### Pièce : cinq sous-vues

L’état réel, les commandes et les modes précèdent les onglets. Les administrateurs disposent de :

| Onglet | Contenu |
| --- | --- |
| Pilotage | Scènes, lancement, import et édition. |
| Lumières | Affectation explicite et informations de groupes. |
| Automatisation | Présence, luminosité et pause manuelle. |
| Ambiances | Associations naturelles et ambiance de base. |
| Réglages | Transitions locales et suppression de la pièce. |

Les utilisateurs ordinaires conservent le pilotage. La vue d’accueil invite à choisir une pièce ; les pièces non configurées restent visibles et expliquent l’action disponible selon les droits. Aucune option métier n’est supprimée par ce découpage.

## Elevation & Depth

La profondeur provient des surfaces du thème, des lignes de séparation et de la teinte de sélection. Le panneau n’ajoute aucune ombre. Les rangées d’actions, listes et groupes de réglages restent au niveau du contenu ; les aides se déplient dans le flux. Les menus d’actions des scènes reviennent à la ligne lorsqu’ils sont ouverts.

**The Surfaces simples Rule.** Les surfaces restent sans ombre ajoutée par Halo. Les fonds du thème, les séparateurs et la sélection teintée suffisent à distinguer les niveaux.

Le focus utilise un contour visible dans la couleur d’accent, décalé du contrôle. La sélection active du sélecteur d’entités possède aussi un contour interne. Les boutons ne bougent pas au survol : seules leurs couleurs et bordures changent avec la durée courte du thème. La préférence `prefers-reduced-motion` supprime les animations et transitions du panneau. Ce mouvement d’interface est distinct des durées appliquées aux lampes.

## Shapes

Les contrôles, sélecteurs, rangées sélectionnées et conditions reprennent le rayon de contrôle Home Assistant défini dans le frontmatter. Les zones de contenu principales sont des panneaux et sections séparés par des lignes, sans enveloppe arrondie systématique. Les conditions imbriquées réduisent leur cadre à des séparateurs ; les onglets globaux gardent un bord droit et un indicateur inférieur.

Les icônes du panneau sont monochromes et reprennent la couleur de leur contexte ou de leur état. Le lotus est l’icône native `mdi:spa`. Le contrôle de suppression d’une sélection utilise un SVG embarqué ; aucun caractère typographique ne remplace une icône.

## Components

### Boutons, navigation et champs

Les boutons secondaires utilisent la surface et le contour du thème ; les actions principales utilisent l’accent. Le survol des boutons secondaires change le fond et le contour ; celui du bouton principal conserve l’accent avec un léger assombrissement. Les états désactivés utilisent les couleurs prévues par Home Assistant et conservent leur libellé. Les boutons d’icône possèdent un nom accessible.

La navigation globale reprend les couleurs de l’en-tête et souligne la page courante. Les onglets de pièce marquent l’état sélectionné par l’accent et un fond teinté. Ils exposent un `tablist`, un panneau associé et un seul arrêt de tabulation actif ; les flèches, Début et Fin déplacent la sélection et le focus.

Les champs et listes natives reprennent les variables Home Assistant de fond, texte, contour normal et contour de survol. Le champ invalide prend la couleur d’erreur. Les sélecteurs Halo fournissent un champ de recherche, une liste de résultats, un état sélectionné et un état de résultat actif ; leur survol, focus et comportement clavier restent explicites. Les aides détaillées utilisent des sections dépliables nommées par leur sujet.

### Accès, navigation et brouillon

L’ajout de l’unique instance Halo crée automatiquement le panneau, sans carte séparée ni YAML. Les droits sont contrôlés côté serveur ; masquer un contrôle ne suffit pas. Le moteur reste actif sans panneau ouvert, hors libération de la session temporaire d’édition décrite plus bas.

Les changements de pièce, d’onglet ou de profil conservent le brouillon transversal. Une saisie invalide bloque la navigation, ouvre le détail qui la contient si nécessaire et reçoit le focus. La validation serveur reste la garantie finale. Abandonner restaure aussi les champs contenant une saisie invalide ; un conflit de révision garde le brouillon visible et interdit une sauvegarde aveugle.

La barre persistante signale les modifications non enregistrées et propose l’enregistrement ou l’abandon. Avec un brouillon sur une pièce déjà enregistrée, l’allumage et l’extinction restent accessibles ; les modes et la reprise demandent d’enregistrer ou d’abandonner. Pour une nouvelle pièce, les commandes attendent sa première sauvegarde. Le texte d’aide distingue ces deux situations.

L’édition réelle bloque la navigation jusqu’à sa fin. Après import ou édition, le panneau revient au pilotage avec un focus cohérent : nouvelle scène importée, action d’origine après annulation, ou scène réglée après édition.

### Configuration et pilotage d’une pièce

**Statut : implémenté dans la première version de développement ; validation matérielle à réaliser.**

#### Lumières et capacités

Le sélecteur présente d’abord les lumières rattachées à la pièce dans Home Assistant, puis permet de rechercher les autres entités `light`. L’affectation est explicite : aucune lumière n’est ajoutée automatiquement à la configuration Halo.

Les listes précisent si l’entité est un groupe Home Assistant ou une lumière individuelle, et affichent les groupes d’appartenance connus ainsi que les membres visibles d’un groupe. L’absence de groupe connu ne prétend pas exclure un regroupement non exposé par l’intégration de la lampe. Ces indications ne désignent pas les associations de profils naturels Halo.

Les groupes fournis par Philips Hue sont également reconnus. Un groupe reste indiqué comme tel lorsque son intégration n’expose pas ses membres ; aucune appartenance n’est inventée.

Chaque sélection d’entité propose une recherche immédiate par nom et identifiant, insensible à la casse et aux accents, avec navigation au clavier et choix à la souris ou au toucher. La sélection courante reste lisible ; quitter une recherche sans choisir conserve cette sélection. Les cas sans résultat et les entités sélectionnées devenues indisponibles sont explicites. Les listes de lampes de la pièce, des associations naturelles, de l’ambiance de base et des scènes proposent aussi un filtre.

L’utilisation du sélecteur natif Home Assistant partout est demandée, mais reste **non implémentée** : le panneau ne dispose pas d’un mécanisme public de chargement identifié pour ce composant. Les sélecteurs Halo restent en place ; ils ne sont pas présentés comme natifs. La fenêtre native des lampes dans l’éditeur de scènes utilise, elle, une action publique documentée.

Une lampe ne peut appartenir qu’à une pièce Halo et qu’à une association de profil naturel au sein de cette pièce. Les lumières générées par Halo sont exclues de la sélection. L’interface doit rendre ces contraintes compréhensibles au moment de l’affectation.

Les contrôles correspondent aux capacités réellement annoncées par chaque lampe :

| Capacité | Contrôles de scène ou d’ambiance de base | Affectation naturelle |
| --- | --- | --- |
| Marche/arrêt | Allumer et éteindre. | Non disponible. |
| Variation | Marche/arrêt et luminosité. | Luminosité uniquement. |
| Température de blanc | Marche/arrêt, luminosité et température dans la plage disponible. | Luminosité et température de blanc. |
| Couleur sans température de blanc | Marche/arrêt, luminosité et couleur. | Luminosité et approximation du blanc par la couleur disponible. |

#### Modes et commandes

La page de pièce expose les commandes correspondant à l’appareil Home Assistant : allumer/éteindre la pièce, activer/désactiver les automatismes, activer/désactiver la lumière naturelle, reprendre l’automatisation et lancer les scènes.

- Les automatismes sont désactivés lors de la première configuration d’une pièce jusqu’à leur activation par l’utilisateur.
- Désactiver l’automatisation conserve les réglages et l’état des lampes ; les commandes explicites restent accessibles.
- La commande de reprise réactive l’automatisation, annule la pause manuelle et réévalue la pièce.
- L’état allumé/éteint de la pièce reflète les lampes réelles : allumé dès qu’une lampe est allumée, indisponible lorsqu’aucune lampe n’est disponible.
- L’ambiance de base permet d’enregistrer les réglages de référence par lampe. Pour une lampe sans réglage enregistré, l’interface explique que l’allumage conserve les réglages propres à la lampe.

L’appareil Home Assistant de chaque pièce expose également un capteur **État** (`Status`). Cet affichage synthétique distingue **Éteint**, **Manuel**, **Lumière naturelle** et le nom de la scène active, sans traduire les noms personnalisés. L’indisponibilité de toutes les lampes reste un état indisponible, jamais une extinction supposée. L’extinction réelle prime sur le mode ; l’édition en direct apparaît comme manuelle. Une scène explicitement lancée reste identifiable pendant sa pause, y compris lorsque les automatismes sont désactivés. Les états fixes suivent les traductions natives anglaises/françaises de Home Assistant. Le capteur ne remplace pas les retours détaillés du panneau sur les pauses, l’absence, la luminosité et les données indisponibles. Il est implémenté, avec des tests locaux du moteur et des plateformes Home Assistant utilisant des lampes simulées ; aucun essai navigateur ou matériel n’est revendiqué pour cet ajout.

#### Présence, luminosité et pause manuelle

La configuration de présence permet de choisir une entité de mouvement, de présence ou personnalisée et de renseigner les états signifiant « présent ». Le délai d’absence est modifiable, avec une valeur initiale de **0 seconde**.

Le capteur de luminosité est facultatif. Lorsqu’il est configuré, l’utilisateur renseigne le seuil et l’hystérésis, initialement à zéro. L’interface affiche les seuils effectifs bas et haut et permet de choisir entre l’autorisation d’allumage seule et l’extinction lorsque la luminosité devient suffisante. Cette extinction est désactivée par défaut ; son délai de confirmation initial est de **30 secondes**.

Les libellés du seuil, de l’hystérésis et des seuils effectifs affichent l’unité `unit_of_measurement` du capteur sélectionné (`lx`, `%` ou autre unité déclarée). Sans unité déclarée, aucun suffixe n’est supposé. Changer de capteur conserve les valeurs numériques ; aucune conversion entre lux et pourcentage n’est appliquée.

La pause manuelle couvre toute la pièce. Elle concerne les modifications de couleur ou de luminosité, les allumages, les extinctions et les lancements explicites de scènes. Ses réglages comprennent :

- Une durée modifiable, initialement **120 minutes**.
- L’autorisation des extinctions automatiques sur absence et sur forte luminosité pendant la pause, **configurable par pièce et activée par défaut**.
- Une explication de la reprise : expiration du délai, retour après une absence continue atteignant le maximum entre délai d’absence local et protection globale, ou commande de reprise.

L’affichage distingue cette pause de la désactivation générale de l’automatisation et de la suspension temporaire liée à l’édition d’une scène. Une extinction manuelle ne doit pas faire disparaître immédiatement l’indication de pause.

### Protection globale contre les pertes de présence

**Rallumage rapide et protection de la pause manuelle implémentés et testés localement, sans validation matérielle ni déploiement domestique pour cet ajout.** Les **Réglages globaux** présentent la section **« Protection contre les pertes de présence »** (`Protection against presence dropouts`) et son champ numérique **« Délai de protection de présence (secondes) »** (`Presence protection delay (seconds)`), initialement à **30**. Le champ est obligatoire, accepte les valeurs finies de **0 à 604 800** et utilise les contrôles, couleurs, focus et erreurs du thème Home Assistant.

Une aide dépliable **« Fonctionnement »** conserve la compacité et distingue trois points :

- Après une extinction automatique pour absence, un retour avant l’expiration de cette durée ignore ponctuellement le capteur lumineux et utilise la transition d’allumage habituel. Ce rallumage concerne uniquement les pièces sans extinction sur forte luminosité et respecte une pause encore active.
- Dans toutes les pièces, le retour ne termine une pause manuelle qu’après une absence continue atteignant à la fois ce délai global et le délai d’absence local. L’indisponibilité du détecteur interrompt cette continuité ; l’expiration propre de pause et la commande de reprise restent distinctes.
- **0** désactive le rallumage rapide et le minimum supplémentaire de protection de la pause, sans supprimer le délai d’absence local ni modifier celui de l’extinction automatique.

Ce champ suit les droits administrateur, le brouillon transversal, la validation avant navigation et la barre d’enregistrement existants. Les valeurs déjà enregistrées restent visibles ; une ancienne configuration sans ce champ affiche **30 secondes**. Le contenu de l’aide et les erreurs sont disponibles en anglais et en français ; aucune nouvelle palette ni composant privé Home Assistant n’est nécessaire.

### Profils de lumière naturelle

**Statut : implémenté dans la première version de développement ; validation matérielle à réaliser.**

L’action **Nouveau profil** préremplit la luminosité à **40 % pour −20°** et **100 % pour 20°**, et la température à **2 000 K pour 0°** et **5 500 K pour 20°**. Les courbes sont linéaires, avec matin et soir liés. Ces valeurs restent modifiables et n’écrasent pas celles des profils existants.

La vue dédiée aux profils permet de créer, nommer et modifier les profils réutilisables, avec un seul éditeur affiché à la fois. L’entité soleil se sélectionne dans les réglages globaux. L’éditeur de profil présente séparément :

- La courbe de température de blanc : deux hauteurs solaires et leurs températures en kelvins.
- La courbe de luminosité : deux hauteurs solaires et leurs luminosités en pourcentage.
- Un choix du type de courbe pour la luminosité et pour la température : **Linéaire** ou **Accélération et décélération progressives**.
- Un aperçu graphique montrant le type sélectionné entre les bornes et les valeurs constantes au-delà.

Le sélecteur **« Type de courbe »** accompagne les réglages de chaque courbe. **Linéaire** est la valeur initiale et le repli pour les profils existants sans ce réglage. Une aide décrit la progression : constante par degré de hauteur solaire en linéaire ; lente près des deux bornes, avec accélération puis décélération dans le mode progressif. L’aperçu montre une courbe en S raccordée doucement aux plateaux, y compris au soleil descendant. Il ne s’agit pas d’une durée en secondes. Le changement de type met à jour l’aperçu avant l’enregistrement. Les anciennes sélections d’accélération progressive affichent et utilisent ce comportement corrigé.

Les champs de hauteur solaire conservent les décimales. Les unités doivent être explicites, sans mélanger hauteur du soleil, température de blanc et luminosité.

L’axe horizontal des aperçus affiche les deux hauteurs solaires saisies, avec leurs graduations à la position exacte des seuils de la courbe. Par exemple, les libellés **−6°** et **45°** se placent au début et à la fin de la pente ; les marges utilisées pour montrer les plateaux ne sont pas étiquetées comme des seuils. La précision décimale est conservée et les seuils proches restent lisibles.

La case **« Lier le matin et le soir »** est cochée par défaut. Lorsqu’elle est décochée, l’éditeur permet de définir distinctement les courbes du soleil montant et descendant ; l’aperçu les distingue.

Cela inclut le type de courbe : les sélecteurs de luminosité et de température restent indépendants, et chaque période dispose de ses propres choix lorsqu’elle est dissociée.

Dans chaque pièce, l’utilisateur peut créer plusieurs associations entre un profil et des lampes compatibles. Une correction relative de luminosité, par exemple **−30 %**, se règle sur l’association sans modifier le profil partagé. L’interface indique que les valeurs appliquées sont limitées aux capacités de chaque lampe et que les ajustements naturels ne rallument pas les lampes éteintes.

L’indisponibilité du soleil doit apparaître comme une suspension des ajustements naturels, et non comme une hauteur solaire égale à zéro.

### Scènes, conditions et édition en direct

**Statut : implémenté dans la première version de développement ; validation matérielle à réaliser.**

#### Liste et conditions

Les scènes appartiennent à une pièce et utilisent ses lumières sélectionnées. Leur ordre dans la liste définit leur priorité : la première scène dont les conditions sont remplies est sélectionnée, une seule à la fois. La liste permet de déplacer les scènes et propose également des boutons **monter/descendre**. Les actions de lancement et de réglage restent visibles ; déplacement et suppression sont regroupés dans un menu par ligne. Les conditions et l’option d’allumage se déplient dans l’éditeur.

L’éditeur de conditions propose les états d’entités, les seuils numériques, les horaires et les conditions solaires. Il permet de les combiner avec **ET**, **OU** et **NON**, sans imposer de YAML.

Chaque scène possède une option indiquant si elle **peut déclencher l’allumage**. Son explication précise la différence :

- Activée, la scène peut allumer et maintenir son ambiance indépendamment de la présence et de la luminosité.
- Désactivée, la scène règle l’ambiance lorsque la pièce doit être allumée.

Les deux modes respectent la désactivation générale de l’automatisation et la pause manuelle. La scène sélectionnée prime sur la lumière naturelle ; sa sortie entraîne la sélection de la suivante ou le retour au fonctionnement normal. Les lampes prévues éteintes dans la scène le restent à l’allumage de la pièce.

Le lancement explicite d’une scène applique son ambiance et déclenche la pause manuelle commune ; ce comportement doit être identifiable depuis le panneau.

#### Import d’une scène Home Assistant

**Implémenté ; vérifié dans Home Assistant isolé avec des lampes simulées.** Dans une pièce enregistrée, l’action administrateur **« Importer depuis Home Assistant »** ouvre une recherche de scène. Le formulaire présente un nom modifiable, la liste des lampes retenues et le nombre d’entités ignorées. Il explique que les autres lampes restent inchangées et que l’import ne commande aucune lampe. Les scènes inaccessibles, les erreurs de lecture et l’absence de lampes communes ont un retour explicite.

Confirmer ajoute une nouvelle scène au brouillon, en dernière position ; la barre d’enregistrement reste le point de sauvegarde ou d’abandon. Annuler le formulaire conserve le brouillon précédent. Les changements non enregistrés doivent être résolus avant de commencer l’import. Le lancement des scènes est désactivé tant qu’il reste des modifications non enregistrées. L’import ne lance pas l’éditeur en direct ni la scène source ; l’utilisateur peut ensuite modifier la copie avec le parcours habituel.

#### Réglage des lampes réelles

L’éditeur présente une liste Halo recherchable des lampes avec leur état réel et leur effet actif, lorsque disponible. Un clic ouvre la fenêtre native Home Assistant, qui fournit les contrôles adaptés à la lampe. Ce parcours est implémenté et vérifié dans le frontend officiel Home Assistant 20260930.2, avec des lampes simulées dans une instance locale. L’ouverture utilise l’action documentée `more-info` ; aucun composant interne Home Assistant n’est copié ou détourné.

Chaque lampe dispose d’une case d’inclusion dans la scène. La réouverture conserve exactement les inclusions enregistrées ; les autres lampes restent proposées mais exclues, sans contrôle matériel tant qu’elles ne sont pas incluses. Une scène manuelle nouvelle inclut toutes les lampes de la pièce. L’aide précise que les lampes exclues restent inchangées au lancement.

L’éditeur indique clairement que les réglages modifient les lampes physiques et que **toute automatisation Halo de cette pièce est temporairement suspendue** pendant l’édition. L’aide précise que les réglages enregistrés, effets compris, sont ceux remontés par la lampe à Home Assistant. Une indisponibilité est visible et ne se traduit jamais par un état éteint inventé.

- Une seule session d’édition peut contrôler une pièce à la fois. Le panneau signale lorsqu’une autre session en détient le contrôle.
- L’état initial est mémorisé avant les réglages.
- **Enregistrer** conserve la scène et rétablit le fonctionnement correspondant aux modes et conditions actuels.
- **Annuler** restaure l’état initial puis libère la suspension.
- Une fermeture ou une perte de connexion libère la session après expiration, sans laisser une suspension permanente.
- L’automatisation ne doit pas être réactivée à la sortie de l’éditeur si elle était désactivée avant l’édition.

Le nom et les conditions de la scène restent dans la vue d’édition Halo. La fenêtre native sert au réglage des lampes ; fermer cette fenêtre ne termine pas la session Halo. L’enregistrement capture côté serveur les états réels après les réglages ; l’annulation restaure l’instantané initial, effets compris. Les contrôles existants de l’ambiance de base restent distincts de ce parcours de scène. Le parcours conserve les mêmes garanties dans la présentation compacte.

### Transitions des lumières

**Statut : implémenté dans la première version de développement ; validation matérielle à réaliser.** Ces transitions portent sur les commandes des lampes. Les animations d’interface restent distinctes et suivent les règles de mouvement décrites plus haut.

Les réglages présentent cinq catégories avec leurs valeurs en **secondes** :

| Catégorie | Déclenchement |
| --- | --- |
| Allumage habituel | Notamment l’arrivée d’une présence, même lorsqu’une scène est sélectionnée. |
| Allumage sur baisse de luminosité | La pièce est occupée et la luminosité devient insuffisante. |
| Ajustement naturel | Modification de l’éclairage d’après un profil naturel. |
| Scène | Activation, changement ou sortie de scène ; comprend une scène provoquant elle-même l’allumage. |
| Extinction | Extinction de la pièce. |

Les valeurs globales initiales sont respectivement **0, 10, 60, 10 et 2 secondes**, dans l’ordre du tableau. Ces nouveaux défauts ne remplacent pas les réglages déjà enregistrés, y compris les champs vides. Pour chaque catégorie, chaque pièce propose trois choix explicites :

1. **Hériter** de la valeur globale, choix initial.
2. **Définir une durée** propre à la pièce.
3. **Ne demander aucune transition**, sans reprendre la valeur globale.

Sur chaque rangée de catégories, les sélecteurs et les champs de durée sont alignés verticalement, même lorsque les titres occupent des nombres de lignes différents. L’alignement s’adapte au nombre de colonnes disponible, dans les réglages globaux comme dans ceux d’une pièce.

Un champ vide en configuration explicite omet le paramètre de transition. Il se distingue de `0`, qui demande une transition immédiate lorsque la lampe le permet. Une lampe sans prise en charge ne reçoit pas ce paramètre. L’interface doit présenter cette distinction sans faire croire qu’une transition est garantie sur tous les équipements.

### États et retours de fonctionnement

**Statut : implémenté dans la première version de développement ; validation matérielle à réaliser.**

La pièce présente son état réel et la raison du comportement courant. Les informations à rendre explicites comprennent :

- La scène sélectionnée et sa priorité, ou le fonctionnement par ambiance de base/lumière naturelle.
- Les modes d’automatisation et de lumière naturelle activés ou désactivés.
- La pause manuelle et la suspension temporaire d’édition.
- L’absence, la luminosité suffisante et les temporisations correspondantes lorsqu’elles s’appliquent.
- Une donnée ou une lampe indisponible.

Une mesure absente ou inconnue ne doit jamais être affichée comme une valeur zéro valide. Les états affichés ne doivent pas présenter une commande envoyée comme un changement matériel déjà confirmé. Les états et échéances sont textuels sous le nom de la pièce ; les notifications informatives et les erreurs disposent d’une zone dédiée. Les actions indisponibles ou en cours sont désactivées sans faire disparaître leur libellé. Les vues vides expliquent le contexte et présentent l’action accessible selon les droits.

## Do's and Don'ts

### Do:

- Do préserver toutes les options métier dans leurs sous-vues et utiliser des aides dépliables pour le détail.
- Do suivre les variables du thème Home Assistant pour les surfaces, textes, états, champs, en-tête et typographie.
- Do maintenir des libellés explicites, un focus visible, les parcours clavier et des cibles adaptées au toucher.
- Do conserver le brouillon entre vues, révéler les erreurs de saisie et maintenir la barre de sauvegarde accessible.
- Do distinguer état réel, commande envoyée, pause manuelle, automatisation désactivée et édition réelle.
- Do consigner les écrans, thèmes, langues et états effectivement vérifiés, avec les limites matérielles.

### Don't:

- Don’t imposer une palette Halo ou une police décorative au thème de Home Assistant.
- Don’t transformer la compacité en suppression d’option, de libellé utile ou de garantie d’édition.
- Don’t présenter un sélecteur Halo comme natif ni charger indirectement un composant privé Home Assistant.
- Don’t remplacer une donnée indisponible par zéro ou un état éteint inventé.
- Don’t assimiler un aperçu simulé ou un test dans Home Assistant isolé à une validation sur les lampes du logement.

### Décisions remplacées et points ouverts

La table historique « Règles à définir » est remplacée par les décisions du 9 octobre 2026 : mise en page compacte, hiérarchie courte, thème Home Assistant, formes des contrôles, retours d’état, adaptation mobile, clavier et mouvement réduit sont désormais implémentés. Le glossaire éditorial détaillé reste ouvert. Les règles fonctionnelles, valeurs initiales et garanties d’édition antérieures sont conservées dans les composants ci-dessus et dans `PROJET.md`.

### Vérifications prévues

**La validation exhaustive et les essais sur les lampes du logement restent à réaliser.** Les vérifications locales et les parcours Home Assistant isolés décrits plus haut couvrent une partie de ces points ; leurs résultats et limites figurent dans [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md). La liste complète reste la référence de validation :

- Accès au panneau après l’installation unique, navigation des pièces et droits utilisateur/administrateur.
- Sélection des lumières, contraintes d’affectation et contrôles adaptés aux quatre familles de lampes.
- Lecture des modes, de la pause manuelle et de sa politique d’extinction propre à la pièce, des temporisations et de l’indisponibilité.
- Courbes naturelles, matin/soir liés ou séparés, associations multiples et correction de luminosité visible sans modification du profil partagé.
- Ordre des scènes, conditions combinées, option d’allumage et indication de la scène effectivement sélectionnée.
- Import depuis Home Assistant : recherche, aperçu des lampes retenues et entités ignorées, nom modifiable, annulation, erreurs et sauvegarde avec la barre habituelle, sans commande matérielle.
- Scène partielle : inclusions conservées à la réouverture, cases explicites et lampes exclues inchangées au lancement.
- Clic sur une lampe ouvrant la vraie fenêtre Home Assistant ; effet actif visible au retour, capture des états lors de l’enregistrement et restauration après annulation.
- Édition réelle, enregistrement, annulation, déconnexion et accès concurrent.
- Transitions héritées, propres à la pièce, absentes, égales à zéro ou non prises en charge.
- Protection globale contre les pertes de présence : défaut de 30 secondes, bornes et valeur zéro ; aide distinguant rallumage et protection de pause, délai d’absence local conservé, brouillon et valeurs sauvegardées préservés, traductions anglaises/françaises.
- Français, anglais, repli anglais et préservation des noms personnalisés.

### Suivi des futures règles

Pour chaque règle, consigner son statut (**proposée**, **actée**, **implémentée**, **vérifiée** ou **remplacée**), son périmètre, la décision précise et un exemple ou une référence visuelle si disponible. Relier la règle à la fonctionnalité concernée dans `PROJET.md`.

Documenter les vérifications visuelles avec l’écran, le thème et les états effectivement examinés. Une maquette ou un composant implémenté ne prouve pas que le dashboard complet a été vérifié dans Home Assistant.

Lorsqu’une règle évolue, actualiser la règle et ses exemples dans la même tâche, puis signaler les parties de l’interface qui restent à adapter.
