<p align="center">
  <img src="https://raw.githubusercontent.com/Gnol86/Halo/main/custom_components/halo/brand/icon@2x.png" alt="Lotus de Halo" width="144" height="144">
</p>

# Halo - Home Assistant Light Orchestrator

**Un éclairage qui suit la vie de ta maison, pièce par pièce.**

Halo est une intégration personnalisée Home Assistant qui réunit présence, luminosité ambiante, profils de lumière naturelle et scènes dans un seul outil. Configure tes pièces depuis un panneau dédié dans la barre latérale, laisse Halo gérer l'éclairage quotidien et reprends la main quand tu le souhaites.

[English](../README.md) · **Français** · [Versions](https://github.com/Gnol86/Halo/releases) · [Signaler un problème](https://github.com/Gnol86/Halo/issues)

Une seule intégration couvre ton logement. Le panneau est inclus, suit le thème Home Assistant et s'adapte aux ordinateurs comme aux mobiles. La configuration de Halo ne nécessite ni YAML ni carte de dashboard séparée. Son moteur d'éclairage fonctionne dans Home Assistant et reste actif lorsque le panneau est fermé.

> **État du projet :** Halo est en début de développement, avec des releases GitHub publiées pour une installation comme dépôt personnalisé HACS. Les tests automatisés et les essais ciblés dans une instance Home Assistant isolée utilisent des lampes simulées ; la validation sur les équipements réels du logement reste à compléter. Halo n'est pas encore référencé dans le catalogue HACS par défaut.

## Ce que Halo peut faire

| Fonctionnalité | Ce qu'elle apporte à ton logement |
| --- | --- |
| **Automatisation par pièce** | Allumer à la détection de présence et éteindre après un délai d'absence configurable. Utiliser des seuils de luminosité et une hystérésis pour déterminer quand l'éclairage est nécessaire. |
| **Éclairage sans capteur lumineux** | Autoriser l'éclairage en permanence, pendant une plage horaire quotidienne ou sous une hauteur solaire choisie. Les plages horaires peuvent traverser minuit. |
| **Profils de lumière naturelle** | Adapter la luminosité et la température du blanc à la hauteur du soleil. Réutiliser les profils dans plusieurs pièces, distinguer les courbes du matin et du soir et ajuster la luminosité par groupe de lampes. |
| **Scènes et priorités** | Créer des scènes avec des conditions d'état, de valeur numérique, d'horaire ou de soleil. Classer les scènes par priorité et choisir si chacune peut allumer automatiquement les lumières. |
| **Scènes Home Assistant** | Lier une scène existante pour la lancer directement, ou importer une copie indépendante de ses réglages pour les lampes de la pièce lorsque la configuration source est accessible. |
| **Veilleuses** | Conserver certaines lampes avec des réglages fixes pendant une absence confirmée, tout en éteignant les autres. Les veilleuses suivent l'autorisation d'éclairage de la pièce. |
| **Commandes manuelles** | Une intervention manuelle suspend les changements de scène automatiques et les ajustements naturels pour toute la pièce. Reprendre explicitement ou laisser agir les règles de fin de pause. |
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

1. Ouvre **HACS** dans Home Assistant.
2. Ouvre le menu à trois points et sélectionne **Dépôts personnalisés**.
3. Ajoute `https://github.com/Gnol86/Halo` avec le type **Intégration**.
4. Recherche **Halo** dans HACS et télécharge l'intégration.
5. Redémarre Home Assistant.
6. Dans **Paramètres → Appareils et services → Ajouter une intégration**, recherche **Halo** et confirme l'installation.
7. Ouvre **Halo** dans la barre latérale.

Ajoute Halo une seule fois : la même intégration gère toutes les pièces configurées. Le [guide officiel des dépôts personnalisés HACS](https://www.hacs.xyz/docs/faq/custom_repositories/) détaille l'ajout du dépôt.

### Installation manuelle

1. Télécharge l'archive des sources d'une [version publiée](https://github.com/Gnol86/Halo/releases).
2. Copie son dossier `custom_components/halo` dans le dossier de configuration Home Assistant, de façon à y trouver `custom_components/halo/manifest.json`.
3. Redémarre Home Assistant, puis ajoute **Halo** depuis **Paramètres → Appareils et services → Ajouter une intégration**.

Le panneau compilé et les images de marque sont inclus dans la release. Aucune compilation du frontend n'est nécessaire pour l'installation.

### Mises à jour

Mets Halo à jour avec HACS ou remplace le dossier `custom_components/halo` par celui de la version choisie. Redémarre Home Assistant et recharge ton navigateur pour charger le panneau actualisé. Consulte les [notes de version](https://github.com/Gnol86/Halo/releases) pour les changements et la compatibilité.

## Configurer ta première pièce

1. Ouvre **Halo → Pièces** et sélectionne une pièce Home Assistant.
2. Dans **Lumières**, choisis les lampes que Halo peut piloter. Une lampe appartient à une seule pièce Halo ; les nouvelles lampes découvertes ne sont jamais ajoutées automatiquement.
3. Dans **Automatisation**, sélectionne la source de présence et le délai d'absence. Ajoute un capteur lumineux et ses seuils, ou choisis **Toujours**, **Plage horaire** ou **Hauteur du soleil** sans capteur configuré.
4. Sélectionne **Enregistrer les modifications** pour sauvegarder la pièce. Les automatismes sont désactivés à la création d'une pièce.
5. Dans **Ambiances**, configure si tu le souhaites une ambiance de base, des associations de profils naturels ou des veilleuses. Crée les profils réutilisables dans **Profils de lumière naturelle** et sélectionne l'entité soleil dans **Réglages globaux**. Enregistre les modifications en attente avant d'ouvrir l'éditeur de veilleuse, puis active la veilleuse après avoir configuré ses lampes.
6. Enregistre les dernières modifications, puis active l'interrupteur **Automatisation** de la pièce quand tu es prêt.

Utilise **Pilotage** pour créer ou lancer des scènes et **Réglages** pour personnaliser les transitions de la pièce. Tes modifications restent dans un brouillon commun lorsque tu changes d'onglet, de pièce ou de profil, jusqu'à leur enregistrement ou leur abandon.

Chaque pièce configurée expose aussi des entités Home Assistant : une lumière de commande, un capteur d'état, des interrupteurs d'éclairage automatique et de lumière naturelle, un bouton de reprise et ses scènes. Tu peux les utiliser dans tes propres dashboards et automatisations.

## Comprendre les règles d'éclairage

**Éclairage quotidien.** Lorsque la présence et l'autorisation d'éclairage le permettent, Halo applique la première scène conditionnelle admissible. Si aucune scène ne s'applique, il utilise l'ambiance de base et les profils naturels actifs de la pièce. Une scène explicitement autorisée à allumer peut agir indépendamment de la présence et de la luminosité, tout en respectant les pauses manuelles et la désactivation des automatismes.

**Tes choix manuels.** Modifier une lampe ou lancer explicitement une scène déclenche une pause pour toute la pièce. Elle prend fin à l'expiration de son délai, au retour après une absence confirmée suffisamment longue, ou avec **Reprendre l'automatisation**. L'extinction automatique pendant une pause est configurable par pièce et autorisée par défaut. Une extinction manuelle de toute la pièce bloque le rallumage automatique, veilleuses comprises, pendant cette pause.

**Veilleuses.** Après une absence confirmée, les veilleuses activées remplacent l'éclairage normal lorsque celui-ci est autorisé. Elles s'éteignent à la fermeture de l'autorisation d'éclairage, même si l'extinction automatique de l'éclairage normal est désactivée.

**Scènes liées et importées.** Une scène Home Assistant liée est lancée intégralement et peut commander des appareils extérieurs à la pièce Halo. Halo ne restaure pas ces appareils extérieurs à la fin de la scène. Une copie importée reprend uniquement les lampes correspondantes sélectionnées dans la pièce et reste indépendante des changements ultérieurs de la source. Les scènes dont les réglages ne sont pas exposés, notamment certaines scènes de fournisseurs, peuvent être liées sans être nécessairement importables.

**Données indisponibles.** Une mesure manquante n'est jamais interprétée comme zéro ou comme une absence confirmée. Un capteur lumineux configuré reste prioritaire même lorsqu'il est indisponible ; Halo ne bascule pas silencieusement sur les règles horaires ou solaires. Les ajustements naturels sont également suspendus lorsque les données solaires nécessaires sont indisponibles.

## Documentation et développement

La documentation détaillée du projet est actuellement en français.

- [Spécification fonctionnelle](../PROJET.md) — règles d'éclairage, valeurs par défaut et critères d'acceptation.
- [Design du panneau](../DESIGN.md) — navigation, interactions et intégration au thème Home Assistant.
- [Architecture](ARCHITECTURE.md) — moteur, stockage, entités et contrats du panneau.
- [Guide de développement](DEVELOPMENT.md) — environnement, vérifications et résultats de validation consignés.
- [Feuille de route](ROADMAP.md) — travail réalisé et validations restantes.
- [HACS et releases](HACS.md) — distribution et procédure de publication.

Le [rapport de recette générale](QA-2026-10-10.md) et le [rapport des autorisations d'éclairage](QA-LIGHTING-FALLBACK-2026-10-10.md) précisent le périmètre et les limites des vérifications locales. Le comportement matériel, les effets propres aux fournisseurs et les transitions physiques restent à valider sur les équipements cibles.

Les signalements de problèmes et les contributions sont les bienvenus. Pour [ouvrir un ticket](https://github.com/Gnol86/Halo/issues), indique tes versions de Halo et de Home Assistant, l'intégration des lampes concernées, les étapes de reproduction et le comportement attendu puis observé. Consulte le guide de développement avant de modifier le code.

## Soutien et licence

Si Halo t'est utile, tu peux [soutenir son développement sur Buy Me a Coffee](https://www.buymeacoffee.com/gnol86).

Halo est distribué sous [licence MIT](../LICENSE).
