<p align="center">
  <img src="https://raw.githubusercontent.com/Gnol86/Halo/main/custom_components/halo/brand/icon@2x.png" alt="Lotus de Halo" width="144" height="144">
</p>

# Halo - Home Assistant Light Orchestrator

**Un éclairage qui suit la vie de ta maison, pièce par pièce.**

Halo est une intégration personnalisée Home Assistant qui réunit présence, luminosité ambiante, profils de lumière naturelle et scènes dans un seul outil. Configure tes pièces depuis un panneau dédié dans la barre latérale, laisse Halo gérer l'éclairage quotidien et reprends la main quand tu le souhaites.

[English](../README.md) · **Français** · [Versions](https://github.com/Gnol86/Halo/releases) · [Signaler un problème](https://github.com/Gnol86/Halo/issues)

Une seule intégration couvre ton logement. Le panneau est inclus, suit le thème Home Assistant et s'adapte aux ordinateurs comme aux mobiles. La configuration de Halo ne nécessite ni YAML ni carte de dashboard séparée. Son moteur d'éclairage fonctionne dans Home Assistant et reste actif lorsque le panneau est fermé.

<a href="https://raw.githubusercontent.com/Gnol86/Halo/main/docs/images/room-control-fr.png">
  <img src="https://raw.githubusercontent.com/Gnol86/Halo/main/docs/images/room-control-fr.png" alt="Aperçu simulé du pilotage Halo : huit pièces, dont six configurées, lumière naturelle dans le salon et trois scènes Halo" width="1000">
</a>

*Pilote toutes tes pièces depuis un seul panneau. Repère celles qui suivent une scène, la lumière naturelle, une commande directe ou une veilleuse, puis lance une ambiance en un clic.*

Les captures montrent l’aperçu local du panneau Halo, avec des pièces fictives et des appareils simulés. Aucune instance du logement n’est connectée. Clique sur une capture pour l’afficher en pleine taille.

> **État du projet :** Halo est en début de développement et a été [accepté dans le catalogue HACS par défaut](https://github.com/hacs/default/pull/11771) le 21 octobre 2026. Recherche directement **Halo** dans HACS pour installer une version publiée. Les tests automatisés et les essais ciblés dans une instance Home Assistant isolée utilisent des lampes simulées ; la validation sur les équipements réels du logement reste à compléter.

## Ce que Halo peut faire

| Fonctionnalité | Ce qu'elle apporte à ton logement |
| --- | --- |
| **Automatisation par pièce** | Allumer à la détection de présence et éteindre après un délai d'absence configurable. Utiliser des seuils de luminosité et une hystérésis pour déterminer quand l'éclairage est nécessaire. |
| **Éclairage sans capteur lumineux** | Autoriser l'éclairage en permanence, pendant une plage horaire quotidienne ou sous une hauteur solaire choisie. Les plages horaires peuvent traverser minuit. |
| **Profils de lumière naturelle** | Adapter la luminosité et la température du blanc à la hauteur du soleil. Réutiliser les profils dans plusieurs pièces, distinguer les courbes du matin et du soir et ajuster la luminosité par groupe de lampes. |
| **Scènes et priorités** | Créer des scènes avec des conditions d'état, de valeur numérique, d'horaire ou de soleil. Classer les scènes par priorité et choisir si chacune peut allumer automatiquement les lumières. |
| **Scènes Home Assistant** | Lier une scène existante pour la lancer directement, ou importer une copie indépendante de ses réglages pour les lampes de la pièce lorsque la configuration source est accessible. |
| **Veilleuses** | Conserver certaines lampes avec des réglages fixes pendant une absence confirmée, tout en éteignant les autres. Les veilleuses suivent l'autorisation d'éclairage de la pièce. |
| **Commande directe** | Allume, éteins et lance des scènes sans suspendre les automatismes de la pièce. Désactive **Automatisation** pour garder la main. |
| **Transitions** | Définir des durées globales pour l'éclairage quotidien, les ajustements naturels, les scènes et l'extinction, avec des réglages propres à chaque pièce selon les capacités des lampes. |

Le panneau propose une recherche des pièces et des entités, un état actualisé et une édition des scènes avec les commandes natives des lampes Home Assistant. L'anglais et le français sont inclus : le panneau suit la langue de l'interface de chaque utilisateur, en français pour ses variantes régionales et en anglais autrement. Les noms personnalisés des pièces, profils et scènes restent inchangés.

## Prérequis

- **Home Assistant 2026.10.0 ou plus récent.**
- Des lumières déjà disponibles comme entités `light` dans Home Assistant et des pièces définies pour celles que tu souhaites configurer.
- Un compte administrateur pour installer Halo et modifier sa configuration. Les autres utilisateurs peuvent piloter les pièces et lancer les scènes.
- Une source de présence pour les automatismes liés à la présence et les veilleuses. Le capteur lumineux est facultatif ; une entité soleil est nécessaire pour les profils naturels et l'autorisation d'éclairage solaire.
- HACS pour la méthode d'installation ci-dessous, ou un accès au dossier de configuration Home Assistant pour l'installation manuelle.

Halo utilise les capacités exposées par les intégrations de tes lampes : marche/arrêt, variation, température du blanc, couleurs et effets lorsqu'ils sont pris en charge. Les profils naturels nécessitent des lampes variables en luminosité ; les lampes uniquement colorées peuvent approcher une température de blanc avec leur mode de couleur.

## Installation

### Avec HACS

Ouvre directement Halo dans HACS :

[![Ouvrir Halo dans HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Gnol86&repository=Halo&category=integration)

1. Ouvre **HACS** dans Home Assistant.
2. Recherche **Halo**, ouvre sa fiche et télécharge l'intégration.
3. Redémarre Home Assistant.
4. Dans **Paramètres → Appareils et services → Ajouter une intégration**, recherche **Halo** et confirme l'installation.
5. Ouvre **Halo** dans la barre latérale.

Après avoir téléchargé Halo et redémarré Home Assistant, tu peux aussi ouvrir directement son assistant de configuration :

[![Ajouter l’intégration Halo à Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=halo)

Lors de la première utilisation, My Home Assistant peut te demander l’URL de ton instance Home Assistant.

Ajoute Halo une seule fois : la même intégration gère toutes les pièces configurées.

#### Si Halo n'apparaît pas dans HACS

L'ajout au catalogue a été fusionné le 21 octobre 2026. HACS [annonce un délai pouvant atteindre 8 heures](https://github.com/hacs/default/pull/11771#issuecomment-6316138368) avant l'apparition des nouveaux dépôts acceptés. Si Halo n'est pas référencé dans ton instance, tu peux utiliser un dépôt personnalisé comme solution de secours :

1. Dans HACS, ouvre le menu à trois points et sélectionne **Dépôts personnalisés**.
2. Ajoute `https://github.com/Gnol86/Halo` avec le type **Intégration**.
3. Recherche **Halo** et poursuis avec les étapes de téléchargement et de configuration ci-dessus.

Le [guide officiel des dépôts personnalisés HACS](https://www.hacs.xyz/docs/faq/custom_repositories/) détaille cette solution de secours.

### Installation manuelle

1. Télécharge l'archive des sources d'une [version publiée](https://github.com/Gnol86/Halo/releases).
2. Copie son dossier `custom_components/halo` dans le dossier de configuration Home Assistant, de façon à y trouver `custom_components/halo/manifest.json`.
3. Redémarre Home Assistant, puis ajoute **Halo** depuis **Paramètres → Appareils et services → Ajouter une intégration**.

Le panneau compilé et les images de marque sont inclus dans la release. Aucune compilation du frontend n'est nécessaire pour l'installation.

### Mises à jour

Mets Halo à jour avec HACS ou remplace le dossier `custom_components/halo` par celui de la version choisie. Redémarre Home Assistant et recharge ton navigateur pour charger le panneau actualisé. Consulte les [notes de version](https://github.com/Gnol86/Halo/releases) pour les changements et la compatibilité.

## Configurer ta première pièce

**À partir de la version 0.2.1 :** une nouvelle installation crée automatiquement un profil réutilisable **Natural light**. Ses courbes sont linéaires : luminosité de **40 % à −20°** à **100 % à 20°**, température du blanc de **2 000 K à 0°** à **5 500 K à 20°**, avec matin et soir liés. Tu peux le renommer, le régler ou le supprimer dans **Profils de lumière naturelle**, puis l'associer aux lampes dans l'onglet **Ambiances** de chaque pièce. Les installations existantes conservent leurs profils, y compris une liste vide ; un profil supprimé ne revient pas au redémarrage.

1. Ouvre **Halo → Pièces** et sélectionne une pièce Home Assistant.
2. Dans **Lumières**, choisis les lampes que Halo peut piloter. Une lampe appartient à une seule pièce Halo ; les nouvelles lampes découvertes ne sont jamais ajoutées automatiquement.
3. Dans **Automatisation**, sélectionne la source de présence et le délai d'absence. Ajoute un capteur lumineux et ses seuils, ou choisis **Toujours**, **Plage horaire** ou **Hauteur du soleil** sans capteur configuré.
4. Sélectionne **Enregistrer les modifications** pour sauvegarder la pièce. Les automatismes sont désactivés à la création d'une pièce.
5. Dans **Ambiances**, configure si tu le souhaites une ambiance de base, des associations de profils naturels ou des veilleuses. Règle ou crée les profils réutilisables dans **Profils de lumière naturelle** et sélectionne l'entité soleil dans **Réglages globaux**. Enregistre les modifications en attente avant d'ouvrir l'éditeur de veilleuse, puis active la veilleuse après avoir configuré ses lampes.
6. Enregistre les dernières modifications, puis active l'interrupteur **Automatisation** de la pièce quand tu es prêt.

Utilise **Pilotage** pour créer ou lancer des scènes et **Réglages** pour personnaliser les transitions de la pièce. Tes modifications restent dans un brouillon commun lorsque tu changes d'onglet, de pièce ou de profil, jusqu'à leur enregistrement ou leur abandon.

Chaque pièce configurée expose aussi des entités Home Assistant : une lumière de commande, un capteur d'état, des interrupteurs d'éclairage automatique et de lumière naturelle et ses scènes. Tu peux les utiliser dans tes propres dashboards et automatisations.

## Le panneau en détail

### Présence et luminosité ambiante

Choisis une source de présence, laisse un délai avant d'éteindre une pièce vide et règle le seuil lumineux ainsi que l'hystérésis. Les valeurs actuelles des capteurs t'aident à comprendre quand Halo autorise l'éclairage.

<a href="https://raw.githubusercontent.com/Gnol86/Halo/main/docs/images/room-automation-fr.png">
  <img src="https://raw.githubusercontent.com/Gnol86/Halo/main/docs/images/room-automation-fr.png" alt="Aperçu simulé de l’automatisation du salon avec un capteur de présence, un délai d’absence de zéro seconde, un seuil d’allumage de 50 lux et une hystérésis de 20 lux" width="1000">
</a>

### Profils de lumière naturelle

**[Bêta 0.4.0b1 — éditeur visuel de profils](https://github.com/Gnol86/Halo/releases/tag/v0.4.0b1) :** l’éditeur réunit désormais une journée schématique, le parcours du soleil, une courbe de luminosité et un remplissage représentant la température du blanc. L’aperçu utilise la hauteur solaire, sans horaires ni calcul géographique, et ne commande aucune lampe. Les profils existants et leur fonctionnement selon le soleil restent compatibles.

**0.3.1 reste la dernière version stable.** L’essai de la bêta est facultatif : pour inclure les préversions dans les recherches de mises à jour HACS de Halo, active son entité interrupteur HACS de préversions si elle est désactivée, puis allume cet interrupteur. La [documentation des interrupteurs HACS](https://www.hacs.dev/docs/use/entities/switch/) explique ce réglage.

Déplace indépendamment les repères de luminosité et de température, sélectionne le début ou la fin du matin ou du soir, puis règle les deux curseurs de valeur. Matin et soir restent visibles ensemble : délie-les pour les régler séparément, ou relie-les pour appliquer les réglages du matin aux deux périodes. Les valeurs exactes et les progressions linéaires ou douces restent accessibles dans **Réglages avancés**. Les modifications utilisent le brouillon commun et les actions habituelles d’enregistrement et d’abandon.

<a href="https://raw.githubusercontent.com/Gnol86/Halo/main/docs/images/natural-profiles-fr.png">
  <img src="https://raw.githubusercontent.com/Gnol86/Halo/main/docs/images/natural-profiles-fr.png" alt="Aperçu simulé de l’éditeur de profils naturels avec une journée schématique unique, un soleil en pointillés, une courbe de luminosité remplie selon la température du blanc, des poignées de hauteur indépendantes et des curseurs de valeur, matin et soir liés" width="1000">
</a>

*Aperçu simulé de l’éditeur bêta. Le remplissage aide à comparer le blanc chaud et froid ; il ne reproduit pas l’apparence d’une lampe particulière.*

## Comprendre les règles d'éclairage

**Éclairage quotidien.** Lorsque la présence et l'autorisation d'éclairage le permettent, Halo applique la première scène conditionnelle admissible. Si aucune scène ne s'applique, il utilise l'ambiance de base et les profils naturels actifs de la pièce. Une scène explicitement autorisée à allumer peut agir indépendamment de la présence et de la luminosité, tout en respectant la désactivation des automatismes et l’édition en direct.

**Tes choix manuels.** Les modifications manuelles des lampes et les scènes lancées explicitement sont des commandes ponctuelles. Elles ne suspendent jamais les automatismes de la pièce. Halo n’annule pas immédiatement sa propre commande explicite, mais sa prochaine action automatique normale peut remplacer ce réglage ou cette scène. Pour garder la main, désactive **Automatisation** dans la pièce ; les commandes explicites restent disponibles. L’édition d’une scène en direct suspend toujours temporairement les automatismes pendant ton travail.

**Passage à 0.3.0.** Les pauses manuelles sont entièrement supprimées : détection, délais, réglages, messages d’activité et boutons **Reprendre l’automatisation**. Les anciennes pauses sauvegardées sont effacées avant le démarrage du moteur. Si l’automatisation de la pièce est activée, ses règles normales s’appliquent dès le chargement de la nouvelle version. La protection de présence, la gestion des appareils indisponibles et les garanties de l’édition en direct sont conservées.

Les tableaux de bord ou automatisations personnalisés utilisant les anciens boutons de reprise Halo doivent être adaptés ; utilise l’interrupteur **Automatisation** existant pour activer ou désactiver le pilotage automatique. L’action `resume` de `halo/command` et le champ de statut `pause_until` ne sont plus disponibles. Les anciens champs de configuration `manual_pause` et `allow_off_during_pause` sont retirés au chargement et à l’enregistrement. Le capteur d’état conserve la valeur technique `manual` pour compatibilité, désormais affichée **Commande directe** ; elle n’indique ni ne crée de pause.

**Activité : origine des commandes dans 0.2.2.** L'activité des lampes enregistre les commandes de **Halo** et leur motif : présence, nom personnalisé de la scène, veilleuse, lumière naturelle, commande manuelle ou extinction automatique. Les commandes sont présentées comme des demandes, distinctes de l'état rapporté par la lampe. Lorsque son intégration conserve le contexte, le détail d'activité natif identifie également Halo et le motif comme origine. Les ajustements et les commandes dont le retour perd le contexte conservent une entrée de demande. Les scènes Home Assistant liées enregistrent leur activation sur la scène et ses lampes connues ; Halo n'invente pas le contenu des scènes opaques.

Activité et Recorder doivent être activés et leurs filtres restent applicables. Les messages suivent la langue configurée du serveur Home Assistant (français et ses variantes, anglais autrement), en conservant les noms personnalisés des scènes. Cela ne change pas la langue du panneau de chaque utilisateur et ne complète pas l'ancien historique. Le journal global peut montrer à la fois l'événement d'origine Halo et l'entrée de demande de la cible. L'attribution est testée avec le traitement natif de l'activité et Recorder sur des lampes simulées. L'inspection MCP en lecture seule du 12 octobre 2026 confirme 0.2.2 chargé et les entrées de commandes Halo dans l'activité domestique ; elle ne comprend ni vérification visuelle ni validation matérielle complète.

**Veilleuses.** Après une absence confirmée, les veilleuses activées remplacent l'éclairage normal lorsque celui-ci est autorisé. Elles s'éteignent à la fermeture de l'autorisation d'éclairage, même si l'extinction automatique de l'éclairage normal est désactivée.

**Scènes liées et importées.** Une scène Home Assistant liée est lancée intégralement et peut commander des appareils extérieurs à la pièce Halo. Halo ne restaure pas ces appareils extérieurs à la fin de la scène. Une copie importée reprend uniquement les lampes correspondantes sélectionnées dans la pièce et reste indépendante des changements ultérieurs de la source. Les scènes dont les réglages ne sont pas exposés, notamment certaines scènes de fournisseurs, peuvent être liées sans être nécessairement importables.

**Données indisponibles.** Une mesure manquante n'est jamais interprétée comme zéro ou comme une absence confirmée. Un capteur lumineux configuré reste prioritaire même lorsqu'il est indisponible ; Halo ne bascule pas silencieusement sur les règles horaires ou solaires. Les ajustements naturels sont également suspendus lorsque les données solaires nécessaires sont indisponibles.

## Contribuer

Les signalements de problèmes et les contributions sont les bienvenus. Pour [ouvrir un ticket](https://github.com/Gnol86/Halo/issues), indique tes versions de Halo et de Home Assistant, l'intégration des lampes concernées, les étapes de reproduction et le comportement attendu puis observé.

Lance les vérifications Python depuis la racine du dépôt :

```sh
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
```

Pour modifier le panneau, utilise Node.js 24 et lance `npm ci`, `npm run check`, `npm test` et `npm run build` depuis la racine du dépôt. Inclus le fichier reconstruit `custom_components/halo/frontend/halo-panel.js` avec tes changements. Consulte le [README du panneau](../frontend/README.md) pour l'aperçu simulé et le fonctionnement de l'interface.

Les tests automatisés et les aperçus simulés ne valident ni le comportement matériel, ni les effets propres aux fournisseurs, ni les transitions physiques sur les équipements cibles.

## Soutien et licence

Si Halo t'est utile, tu peux [soutenir son développement sur Buy Me a Coffee](https://buymeacoffee.com/gnol86).

<a href="https://buymeacoffee.com/gnol86">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Soutenir Halo sur Buy Me a Coffee" height="50">
</a>

Halo est distribué sous [licence MIT](../LICENSE).
