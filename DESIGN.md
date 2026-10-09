# Halo — Design du dashboard

Dernière mise à jour : **9 octobre 2026**.

Ce document est la référence des règles de design du dashboard de Halo : apparence, organisation, composants et interactions. Il doit être mis à jour en temps réel, conformément à [AGENTS.md](AGENTS.md). Les fonctionnalités et leurs comportements métier sont définis dans [PROJET.md](PROJET.md). L’état réellement disponible est présenté dans [README.md](README.md).

## État actuel

**Une première version fonctionnelle du dashboard est implémentée.** Son organisation et ses interactions reprennent les règles actées ci-dessous. Des tests DOM et un aperçu dans Chrome avec données simulées vérifient plusieurs parcours, langues, tailles d’écran et thèmes. L’intégration complète du rendu dans Home Assistant et les essais sur des lampes réelles restent à réaliser.

Les choix esthétiques détaillés restent à définir dans la section « Règles à définir ». Les textes français de ce document décrivent les contrôles attendus ; la langue de référence de l’interface sera l’anglais.

## Identité existante

- **Nom :** Halo.
- **Symbole demandé :** une fleur de lotus.
- **Ressources disponibles :** icônes transparentes de 256 et 512 pixels dans `custom_components/halo/brand/`.
- **Source et prompt :** [assets/branding/README.md](assets/branding/README.md).

Le README référence le lotus par une URL absolue GitHub pour permettre son affichage dans la présentation HACS. La liste de HACS 2.0.5 utilise un mécanisme distinct qui ne prend pas encore en charge les icônes embarquées ; ce défaut d’affichage ne remet pas en cause les ressources graphiques. Voir le [diagnostic HACS](docs/HACS.md#affichage-du-lotus).

L’icône actuelle emploie des tons chauds. Ces couleurs ne constituent pas, à elles seules, une palette validée pour le dashboard. L’usage du lotus dans l’interface reste à préciser.

## Accès, navigation et droits

**Statut : implémenté dans la première version de développement ; validation matérielle à réaliser.**

- L’ajout de l’unique instance Halo crée automatiquement un panneau **Halo** dans la barre latérale Home Assistant. Aucune carte séparée ni configuration YAML n’est nécessaire.
- La vue principale présente les pièces de Home Assistant et distingue celles configurées dans Halo des autres.
- Chaque pièce ouvre une page donnant accès à ses lumières, à l’automatisation, aux associations de profils naturels, à l’ambiance de base, aux scènes et aux transitions.
- Une section globale regroupe les profils naturels réutilisables, la sélection de l’entité soleil et les transitions par défaut.
- Les utilisateurs peuvent piloter les pièces et lancer les scènes. La modification de la configuration est réservée aux administrateurs. Ces droits sont contrôlés côté serveur ; masquer un contrôle dans le panneau ne suffit pas.
- Le moteur fonctionne indépendamment de l’ouverture du panneau. Fermer le dashboard ne suspend pas l’automatisation, hors libération de la session temporaire d’édition décrite plus bas.

L’implémentation actuelle utilise une liste de pièces, une page par pièce avec sections et une page globale. Cette présentation fonctionnelle reste ajustable lors de la définition esthétique.

## Configuration et pilotage d’une pièce

**Statut : implémenté dans la première version de développement ; validation matérielle à réaliser.**

### Lumières et capacités

Le sélecteur présente d’abord les lumières rattachées à la pièce dans Home Assistant, puis permet de rechercher les autres entités `light`. L’affectation est explicite : aucune lumière n’est ajoutée automatiquement à la configuration Halo.

Une lampe ne peut appartenir qu’à une pièce Halo et qu’à une association de profil naturel au sein de cette pièce. Les lumières générées par Halo sont exclues de la sélection. L’interface doit rendre ces contraintes compréhensibles au moment de l’affectation.

Les contrôles correspondent aux capacités réellement annoncées par chaque lampe :

| Capacité | Contrôles de scène ou d’ambiance de base | Affectation naturelle |
| --- | --- | --- |
| Marche/arrêt | Allumer et éteindre. | Non disponible. |
| Variation | Marche/arrêt et luminosité. | Luminosité uniquement. |
| Température de blanc | Marche/arrêt, luminosité et température dans la plage disponible. | Luminosité et température de blanc. |
| Couleur sans température de blanc | Marche/arrêt, luminosité et couleur. | Luminosité et approximation du blanc par la couleur disponible. |

### Modes et commandes

La page de pièce expose les commandes correspondant à l’appareil Home Assistant : allumer/éteindre la pièce, activer/désactiver les automatismes, activer/désactiver la lumière naturelle, reprendre l’automatisation et lancer les scènes.

- Les automatismes sont désactivés lors de la première configuration d’une pièce jusqu’à leur activation par l’utilisateur.
- Désactiver l’automatisation conserve les réglages et l’état des lampes ; les commandes explicites restent accessibles.
- La commande de reprise réactive l’automatisation, annule la pause manuelle et réévalue la pièce.
- L’état allumé/éteint de la pièce reflète les lampes réelles : allumé dès qu’une lampe est allumée, indisponible lorsqu’aucune lampe n’est disponible.
- L’ambiance de base permet d’enregistrer les réglages de référence par lampe. Pour une lampe sans réglage enregistré, l’interface explique que l’allumage conserve les réglages propres à la lampe.

### Présence, luminosité et pause manuelle

La configuration de présence permet de choisir une entité de mouvement, de présence ou personnalisée et de renseigner les états signifiant « présent ». Le délai d’absence est modifiable, avec une valeur initiale de **120 secondes**.

Le capteur de luminosité est facultatif. Lorsqu’il est configuré, l’utilisateur renseigne le seuil et l’hystérésis, initialement à zéro. L’interface affiche les seuils effectifs bas et haut et permet de choisir entre l’autorisation d’allumage seule et l’extinction lorsque la luminosité devient suffisante. Cette extinction est désactivée par défaut ; son délai de confirmation initial est de **30 secondes**.

La pause manuelle couvre toute la pièce. Elle concerne les modifications de couleur ou de luminosité, les allumages, les extinctions et les lancements explicites de scènes. Ses réglages comprennent :

- Une durée modifiable, initialement **15 minutes**.
- L’autorisation des extinctions automatiques sur absence et sur forte luminosité pendant la pause, **configurable par pièce et activée par défaut**.
- Une explication de la reprise : expiration du délai, retour après une absence confirmée ou commande de reprise.

L’affichage distingue cette pause de la désactivation générale de l’automatisation et de la suspension temporaire liée à l’édition d’une scène. Une extinction manuelle ne doit pas faire disparaître immédiatement l’indication de pause.

## Profils de lumière naturelle

**Statut : implémenté dans la première version de développement ; validation matérielle à réaliser.**

La configuration globale permet de sélectionner une entité soleil et de créer, nommer et modifier des profils réutilisables. L’éditeur de profil présente séparément :

- La courbe de température de blanc : deux hauteurs solaires et leurs températures en kelvins.
- La courbe de luminosité : deux hauteurs solaires et leurs luminosités en pourcentage.
- Un aperçu graphique montrant l’interpolation linéaire entre les bornes et les valeurs constantes au-delà.

Les champs de hauteur solaire conservent les décimales. Les unités doivent être explicites, sans mélanger hauteur du soleil, température de blanc et luminosité.

La case **« Lier le matin et le soir »** est cochée par défaut. Lorsqu’elle est décochée, l’éditeur permet de définir distinctement les courbes du soleil montant et descendant ; l’aperçu les distingue.

Dans chaque pièce, l’utilisateur peut créer plusieurs associations entre un profil et des lampes compatibles. Une correction relative de luminosité, par exemple **−30 %**, se règle sur l’association sans modifier le profil partagé. L’interface indique que les valeurs appliquées sont limitées aux capacités de chaque lampe et que les ajustements naturels ne rallument pas les lampes éteintes.

L’indisponibilité du soleil doit apparaître comme une suspension des ajustements naturels, et non comme une hauteur solaire égale à zéro.

## Scènes, conditions et édition en direct

**Statut : implémenté dans la première version de développement ; validation matérielle à réaliser.**

### Liste et conditions

Les scènes appartiennent à une pièce et utilisent ses lumières sélectionnées. Leur ordre dans la liste définit leur priorité : la première scène dont les conditions sont remplies est sélectionnée, une seule à la fois. La liste permet de déplacer les scènes et propose également des boutons **monter/descendre**.

L’éditeur de conditions propose les états d’entités, les seuils numériques, les horaires et les conditions solaires. Il permet de les combiner avec **ET**, **OU** et **NON**, sans imposer de YAML.

Chaque scène possède une option indiquant si elle **peut déclencher l’allumage**. Son explication précise la différence :

- Activée, la scène peut allumer et maintenir son ambiance indépendamment de la présence et de la luminosité.
- Désactivée, la scène règle l’ambiance lorsque la pièce doit être allumée.

Les deux modes respectent la désactivation générale de l’automatisation et la pause manuelle. La scène sélectionnée prime sur la lumière naturelle ; sa sortie entraîne la sélection de la suivante ou le retour au fonctionnement normal. Les lampes prévues éteintes dans la scène le restent à l’allumage de la pièce.

Le lancement explicite d’une scène applique son ambiance et déclenche la pause manuelle commune ; ce comportement doit être identifiable depuis le panneau.

### Réglage des lampes réelles

L’éditeur ajuste les lampes en temps réel à partir de contrôles adaptés à leurs capacités. Il indique clairement que les réglages modifient les lampes physiques et que **toute automatisation Halo de cette pièce est temporairement suspendue** pendant l’édition.

- Une seule session d’édition peut contrôler une pièce à la fois. Le panneau signale lorsqu’une autre session en détient le contrôle.
- L’état initial est mémorisé avant les réglages.
- **Enregistrer** conserve la scène et rétablit le fonctionnement correspondant aux modes et conditions actuels.
- **Annuler** restaure l’état initial puis libère la suspension.
- Une fermeture ou une perte de connexion libère la session après expiration, sans laisser une suspension permanente.
- L’automatisation ne doit pas être réactivée à la sortie de l’éditeur si elle était désactivée avant l’édition.

Le nom et les conditions de la scène se configurent dans ce parcours. L’implémentation actuelle les présente avec les contrôles de lampe dans une vue d’édition dédiée ; sa présentation visuelle reste à affiner.

## Transitions des lumières

**Statut : implémenté dans la première version de développement ; validation matérielle à réaliser.** Ces transitions portent sur les commandes des lampes. Les animations de l’interface restent un sujet esthétique distinct, à définir.

Les réglages présentent cinq catégories avec leurs valeurs en **secondes** :

| Catégorie | Déclenchement |
| --- | --- |
| Allumage habituel | Notamment l’arrivée d’une présence, même lorsqu’une scène est sélectionnée. |
| Allumage sur baisse de luminosité | La pièce est occupée et la luminosité devient insuffisante. |
| Ajustement naturel | Modification de l’éclairage d’après un profil naturel. |
| Scène | Activation, changement ou sortie de scène ; comprend une scène provoquant elle-même l’allumage. |
| Extinction | Extinction de la pièce. |

Les valeurs globales sont initialement vides. Pour chaque catégorie, chaque pièce propose trois choix explicites :

1. **Hériter** de la valeur globale, choix initial.
2. **Définir une durée** propre à la pièce.
3. **Ne demander aucune transition**, sans reprendre la valeur globale.

Un champ vide en configuration explicite omet le paramètre de transition. Il se distingue de `0`, qui demande une transition immédiate lorsque la lampe le permet. Une lampe sans prise en charge ne reçoit pas ce paramètre. L’interface doit présenter cette distinction sans faire croire qu’une transition est garantie sur tous les équipements.

## États et retours de fonctionnement

**Statut : implémenté dans la première version de développement ; validation matérielle à réaliser.**

La pièce présente son état réel et la raison du comportement courant. Les informations à rendre explicites comprennent :

- La scène sélectionnée et sa priorité, ou le fonctionnement par ambiance de base/lumière naturelle.
- Les modes d’automatisation et de lumière naturelle activés ou désactivés.
- La pause manuelle et la suspension temporaire d’édition.
- L’absence, la luminosité suffisante et les temporisations correspondantes lorsqu’elles s’appliquent.
- Une donnée ou une lampe indisponible.

Une mesure absente ou inconnue ne doit jamais être affichée comme une valeur zéro valide. Les états affichés ne doivent pas présenter une commande envoyée comme un changement matériel déjà confirmé. Les dispositions visuelles, indicateurs d’attente et messages d’erreur précis restent à concevoir.

## Langues et textes

**Statut : implémenté et testé localement.** Les catalogues anglais et français du panneau et les traductions natives de l’intégration sont présents.

- **L’anglais est la langue de référence.** Tous les textes Halo disposent également d’une traduction française.
- Le panneau suit la langue effective de l’interface Home Assistant de l’utilisateur : français pour `fr` et ses variantes, anglais pour les autres langues.
- Les traductions de l’intégration suivent les mécanismes natifs de Home Assistant.
- Les noms personnalisés de pièces, de profils et de scènes restent inchangés.
- Les identifiants techniques restent indépendants de la langue ; les catalogues doivent permettre l’ajout ultérieur de langues.

La langue de chaque utilisateur est respectée : le panneau n’impose pas une langue unique au logement. Le ton détaillé des messages et le glossaire restent à définir.

## Règles à définir

Les rubriques suivantes servent à recueillir les prochaines décisions ; elles n’imposent encore aucun choix.

| Sujet | Décisions à documenter | Statut |
| --- | --- | --- |
| Mise en page | Disposition des vues actées, hiérarchie visuelle et choix entre onglets, sections ou sous-pages. | À définir |
| Apparence | Palette, typographie, espacements, formes et iconographie. | À définir |
| Composants | Forme visuelle des lumières, commandes et réglages dont le rôle est défini ci-dessus. | À définir |
| Retours d’action | Présentation précise des états actifs, attentes, confirmations et erreurs. | À définir |
| États particuliers | Présentation des listes vides, de l’indisponibilité et du chargement. | À définir |
| Écrans et thèmes | Adaptation au mobile, à la tablette, au bureau et aux thèmes. | À définir |
| Accessibilité | Contrastes, lisibilité, clavier, libellés et zones d’interaction. | À définir |
| Mouvement de l’interface | Animations et comportement avec mouvement réduit ; distincts des transitions des lumières. | À définir |
| Textes | Ton, terminologie et messages précis en anglais et en français. | À définir |

## Vérifications prévues

**Les vérifications complètes dans Home Assistant restent à réaliser.** Les tests locaux et l’aperçu dans Chrome avec données simulées couvrent une partie de ces points ; leurs résultats figurent dans [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md). La liste complète reste la référence de validation :

- Accès au panneau après l’installation unique, navigation des pièces et droits utilisateur/administrateur.
- Sélection des lumières, contraintes d’affectation et contrôles adaptés aux quatre familles de lampes.
- Lecture des modes, de la pause manuelle et de sa politique d’extinction propre à la pièce, des temporisations et de l’indisponibilité.
- Courbes naturelles, matin/soir liés ou séparés, associations multiples et correction de luminosité visible sans modification du profil partagé.
- Ordre des scènes, conditions combinées, option d’allumage et indication de la scène effectivement sélectionnée.
- Édition réelle, enregistrement, annulation, déconnexion et accès concurrent.
- Transitions héritées, propres à la pièce, absentes, égales à zéro ou non prises en charge.
- Français, anglais, repli anglais et préservation des noms personnalisés.

## Suivi des futures règles

Pour chaque règle, consigner son statut (**proposée**, **actée**, **implémentée**, **vérifiée** ou **remplacée**), son périmètre, la décision précise et un exemple ou une référence visuelle si disponible. Relier la règle à la fonctionnalité concernée dans `PROJET.md`.

Documenter les vérifications visuelles avec l’écran, le thème et les états effectivement examinés. Une maquette ou un composant implémenté ne prouve pas que le dashboard complet a été vérifié dans Home Assistant.

Lorsqu’une règle évolue, actualiser la règle et ses exemples dans la même tâche, puis signaler les parties de l’interface qui restent à adapter.
