# Halo — Projet et fonctionnalités

Dernière mise à jour : **9 octobre 2026**.

Ce document est le cahier des charges de Halo : objectifs, fonctionnalités, interactions, architecture et critères de validation. Les comportements ci-dessous sont actés. Une première implémentation de développement existe maintenant ; les statuts et limites de vérification sont précisés ci-dessous. La spécification reste la référence du résultat attendu, et ne prouve pas à elle seule son fonctionnement sur du matériel réel.

Ce document, [DESIGN.md](DESIGN.md) et [README.md](README.md) doivent rester à jour en temps réel, conformément à [AGENTS.md](AGENTS.md). `DESIGN.md` détaille l’organisation et les interactions du dashboard ; la refonte compacte suit le thème Home Assistant. Le README présente les capacités effectivement disponibles. Les jalons se trouvent dans [docs/ROADMAP.md](docs/ROADMAP.md).

## 1. Vision et état du projet

Halo est une intégration personnalisée Home Assistant destinée à gérer toutes les lumières du logement, avec une configuration simple et centralisée. Son domaine est `halo`, son identité est une fleur de lotus et une seule installation couvre l’ensemble du logement.

Le socle initial est implémenté : ajout depuis l’interface Home Assistant, entrée de configuration unique, chargement/déchargement/rechargement, textes de configuration anglais et français, icônes locales, tests et workflows préparés. Les vérifications historiques et leurs limites sont consignées dans [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

Limite vérifiée le 9 octobre 2026 : HACS 2.0.5 ne charge pas les icônes embarquées pour sa liste de dépôts. L’image du README utilise une URL absolue GitHub ; les ressources `brand/` restent celles prévues pour Home Assistant. Le [diagnostic des deux emplacements](docs/HACS.md#affichage-du-lotus) distingue cette limite externe de la correction du README. Le référencement par défaut reste un jalon final.

**Une première implémentation du panneau et du moteur d’éclairage est disponible dans le dépôt.** La refonte compacte est implémentée et vérifiée localement, notamment dans Home Assistant 2026.10.0 isolé avec des lampes simulées. Cela ne vaut ni déploiement dans le logement, ni validation matérielle de tous les parcours. Les résultats et limites sont consignés dans [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

| Ensemble | Statut actuel |
| --- | --- |
| Socle d’intégration et configuration unique | Implémenté ; vérifications initiales décrites dans la documentation de développement. |
| Panneau, configuration des pièces et appareils | Refonte compacte implémentée ; tests de navigation et de brouillons, essais ciblés dans Home Assistant isolé et aperçus adaptatifs. |
| Capteur d’état de chaque pièce | Implémenté ; tests locaux du moteur et des plateformes Home Assistant avec lampes simulées ; validation sur les équipements du logement à réaliser. |
| Présence, luminosité, pause manuelle et reprise | Implémenté ; tests avec capteurs et lampes simulés. |
| Rallumage rapide après absence | Implémenté et testé localement ; validation matérielle et déploiement domestique non réalisés pour cet ajout. |
| Protection de la pause contre les pertes brèves de présence | Implémenté et testé localement ; validation matérielle et déploiement domestique non réalisés pour cet ajout. |
| Ambiance de base et profils naturels | Implémenté ; calculs et adaptation aux capacités testés localement. |
| Scènes, conditions, priorités et édition en direct | Implémenté ; tests locaux des priorités, sessions et restaurations. |
| Transitions globales et par pièce | Implémenté ; paramètres et concurrence testés, comportement matériel à vérifier. |
| Localisation complète et sélection de langue du panneau | Catalogues anglais/français et sélection de langue implémentés ; tests locaux. |
| Direction du dashboard | Actée et implémentée : pilotage prioritaire, liste de pièces et détail, sous-vues compactes et thème Home Assistant sans palette propre. |
| Publication et référencement HACS | Jalon final, après développement et validation. |

## 2. Installation et panneau Halo

### Une seule intégration, toute la configuration dans le panneau

L’utilisateur ajoute Halo une seule fois dans Home Assistant. L’intégration ajoute automatiquement un panneau **Halo** dans la barre latérale, sans configuration YAML ni installation séparée de carte. Toute la configuration fonctionnelle se fait dans ce panneau.

La barre latérale et l’en-tête du panneau utilisent le lotus monochrome natif `mdi:spa`, avec les couleurs du thème Home Assistant. Le panneau n’ajoute pas de bouton de menu dans son en-tête. Ce choix d’interface est distinct des images de marque distribuées pour la présentation de l’intégration dans HACS.

Home Assistant fournit un mécanisme de panneau personnalisé pour cette interface. [Documentation officielle](https://developers.home-assistant.io/docs/frontend/custom-ui/creating-custom-panels/).

Le panneau propose trois entrées : **Pièces**, **Profils de lumière naturelle** et **Réglages globaux**. Les deux dernières sont réservées aux administrateurs.

- Les pièces récupérées depuis Home Assistant sont regroupées dans une liste recherchable, avec état, nombre de lumières et commande d’allumage/extinction. Les pièces non configurées restent identifiables et accessibles pour leur configuration. La liste place les pièces configurées dans le brouillon courant avant les autres, conserve l’ordre fourni par Home Assistant dans chaque catégorie et maintient ce classement pendant la recherche.
- Sur grand écran, la liste reste visible à gauche du détail sélectionné ; sur mobile, la liste et le détail se succèdent avec un retour explicite. L’accueil invite à choisir une pièce.
- Le détail donne d’abord accès à l’état réel, aux commandes et aux modes de la pièce. Ses cinq onglets sont **Pilotage** (scènes), **Lumières** (affectation), **Automatisation** (présence, luminosité, pause), **Ambiances** (associations naturelles et ambiance de base) et **Réglages** (transitions locales et suppression). Les utilisateurs ordinaires conservent le pilotage ; les réglages restent administrateurs.
- Les profils naturels disposent d’une liste et d’un seul éditeur affiché à la fois. L’entité soleil, la durée de protection contre les pertes de présence et les transitions par défaut restent dans les réglages globaux.
- L’état explicite de chaque pièce indique la scène sélectionnée, la lumière naturelle, la pause manuelle, l’absence, la luminosité suffisante ou une donnée indisponible.

Cette organisation compacte remplace la page de longs formulaires simultanés, conformément aux choix du 9 octobre 2026 : pilotage prioritaire, liste/détail et construction directe dans le panneau fonctionnel. Toutes les options métier sont conservées. Les aides détaillées, associations naturelles, réglages individuels de l’ambiance de base et conditions de scène peuvent être dépliés au besoin. Les scènes gardent leurs actions de lancement et de réglage visibles ; déplacement et suppression sont regroupés dans un menu par ligne.

Le panneau reprend les variables du thème Home Assistant pour les couleurs, états, typographie, tailles, espacements, bordures, rayons, en-tête et champs, avec des valeurs de repli lorsqu’une variable manque. Le mode clair/sombre suit Home Assistant et la préférence de mouvement réduit est respectée. Halo n’ajoute pas de palette indépendante.

La fermeture du panneau n’interrompt pas les automatismes.

La barre signalant les modifications non enregistrées reste accessible au bas de la fenêtre pendant le défilement des réglages, sans masquer le contenu.

Les changements d’onglet, de pièce ou de profil conservent le brouillon. Un champ invalide empêche de quitter la sous-vue, est révélé si nécessaire et reçoit le focus ; la validation serveur reste la garantie finale. Abandonner rétablit aussi les champs contenant une saisie invalide. L’édition réelle bloque la navigation jusqu’à sa fin. Import et édition ramènent au pilotage avec un focus cohérent : nouvelle scène importée, action d’origine après annulation, ou scène réglée après édition.

### Accès et droits

Les utilisateurs peuvent piloter les pièces et lancer leurs scènes. Les administrateurs peuvent également modifier la configuration.

Les droits sont contrôlés côté serveur pour les commandes concernées. Masquer un bouton dans l’interface ne constitue pas un contrôle d’autorisation.

## 3. Langues

**L’anglais est la langue de référence de l’intégration.** Les menus, réglages, aides, erreurs et statuts propres à Halo disposent d’une traduction française complète.

- Le dashboard suit la langue effective de l’interface Home Assistant de l’utilisateur.
- `fr` et ses variantes utilisent le français ; toute autre langue utilise l’anglais tant qu’elle n’est pas prise en charge.
- Une traduction manquante utilise le texte anglais de référence.
- Les textes de l’intégration utilisent les mécanismes natifs de traduction Home Assistant.
- Les noms de pièces, profils et scènes saisis ou personnalisés par l’utilisateur sont conservés.
- Les identifiants techniques restent stables et indépendants de la langue.
- Les catalogues permettent l’ajout ultérieur d’autres langues sans réécriture des fonctions.

La préférence d’interface Home Assistant se règle dans le profil utilisateur. Le panneau ne doit donc pas imposer une langue commune à tous les habitants. [Configuration des utilisateurs](https://www.home-assistant.io/docs/configuration/user-configuration/).

## 4. Pièces, lumières et appareils

### Sélection des lumières

Les pièces proviennent du registre Home Assistant. L’utilisateur choisit explicitement les entités `light` gérées dans chacune d’elles. Dans l’onglet **Lumières**, le sélecteur affiche par défaut les lumières rattachées à la pièce dans Home Assistant et conserve, dans un groupe distinct, celles déjà sélectionnées dans cette pièce Halo mais rattachées ailleurs ou sans pièce. La case **« Afficher les lumières des autres pièces »**, décochée par défaut, révèle les autres lampes, y compris celles sans pièce. La recherche filtre uniquement la liste ainsi affichée et n’ouvre pas automatiquement les autres pièces. Ce choix d’affichage ne modifie ni les sélections ni le brouillon ; il revient au masquage au changement de pièce ou au rechargement du panneau. Les lampes affectées à une autre pièce Halo restent non sélectionnables.

Les listes distinguent les entités de groupe Home Assistant des lumières individuelles. Elles indiquent les groupes d’appartenance et leurs membres lorsque Home Assistant expose ces informations, dans la limite des droits de lecture de l’utilisateur. Les groupes non exposés par une intégration ne sont pas déduits du nom des lampes. Ces informations restent distinctes des associations de profils naturels de Halo.

Cela comprend les groupes Philips Hue v1 et v2 : un marqueur de groupe ou les métadonnées du registre permettent de reconnaître leur nature, même sans liste de membres. Les listes et ensembles de membres exposés sont pris en charge ; les appartenances non exposées restent inconnues.

Tous les sélecteurs d’entités proposent une recherche immédiate par nom ou identifiant, insensible à la casse et aux accents. Cela couvre notamment la présence, la luminosité, le soleil et les conditions de scènes. Les listes de lampes de la pièce, des associations naturelles, de l’ambiance de base et des scènes sont également filtrables. Abandonner une recherche ne modifie pas la sélection enregistrée.

**Demande de sélecteurs natifs partout : étudiée, non implémentée.** Aucun mécanisme public de chargement du sélecteur natif dans un panneau personnalisé n’a été identifié dans les documents et sources examinés. Les voies documentées concernent les formulaires natifs et l’éditeur de configuration des cartes. Pour respecter la contrainte de ne pas introduire de solution fragile, les sélecteurs Halo actuels sont conservés ; aucun chargement indirect de Lovelace ni import de fichier interne compilé n’est ajouté. [Diagnostic et alternatives](docs/ARCHITECTURE.md#sélecteurs-dentités-natifs).

- Une lampe appartient à une seule pièce Halo.
- Dans cette pièce, elle appartient au maximum à une association de profil naturel.
- Les lumières générées par Halo sont exclues des sélections, afin d’éviter les boucles de commande.
- Une nouvelle lumière disponible n’est pas ajoutée automatiquement à une configuration existante.
- Un renommage de pièce conserve son identité et ne recrée pas son appareil.

### Appareil et entités de chaque pièce configurée

| Entité | Fonction attendue |
| --- | --- |
| Lumière de la pièce | Allumer selon l’ambiance applicable ; éteindre toutes les lumières sélectionnées. |
| Capteur d’état | Afficher « Éteint », « Manuel », « Lumière naturelle » ou le nom de la scène active. |
| Interrupteur d’éclairage automatique | Autoriser ou suspendre tous les automatismes Halo de la pièce. |
| Interrupteur de lumière naturelle | Activer ou désactiver l’application des profils naturels, sous réserve du mode automatique et des pauses. |
| Bouton de reprise | Réactiver l’automatisation, annuler la pause manuelle et réévaluer la pièce. |
| Entités scène Halo | Permettre le lancement explicite des scènes depuis Home Assistant, notamment d’autres dashboards ou automatisations. |

La lumière de commande reflète les états réels : allumée si au moins une lampe est allumée, éteinte si aucune lampe disponible n’est allumée, indisponible si aucune lampe n’est disponible.

Le capteur **État** (`Status` en anglais) appartient au même appareil. Il se met à jour avec les événements de la pièce, même lorsque le panneau est fermé. Son identité suit l’identifiant stable de la pièce ; un renommage ne le recrée pas. Son ajout, son retrait et son rechargement suivent ceux des autres entités de la pièce.

Son affichage applique les priorités suivantes :

1. **Indisponible** lorsqu’aucune lampe n’est disponible.
2. **Éteint** lorsqu’aucune lampe disponible n’est allumée, même si une pause ou une scène est encore sélectionnée.
3. **Manuel** pendant l’édition réelle d’une scène.
4. Le **nom de la scène active** lorsqu’une scène conditionnelle est effectivement appliquée ou lorsqu’une scène a été lancée explicitement pendant la pause manuelle. Ce dernier cas reste nommé même si l’automatisation générale est désactivée ; une nouvelle intervention manuelle met fin à cette attribution.
5. **Lumière naturelle** lorsque le moteur applique les profils naturels et qu’au moins une lampe concernée est allumée.
6. **Manuel** dans les autres cas allumés, notamment une pause hors scène, l’automatisation désactivée ou l’ambiance de base sans profil naturel actif.

Les états fixes `off`, `manual` et `natural` disposent de traductions natives Home Assistant en anglais et en français. Les noms de scène sont conservés sans traduction. Ce capteur synthétique peut être utilisé dans les autres dashboards et automatisations ; il ne remplace pas le statut détaillé du panneau, qui continue à expliquer présence, luminosité, pauses et indisponibilités.

Pour les automatisations, l’attribut `mode` conserve une valeur stable (`off`, `manual`, `natural` ou `scene`), accompagnée de `scene_id` et `scene_name` pour une scène active. Si le nom est exactement `off`, `manual`, `natural`, `unknown` ou `unavailable`, la valeur du capteur devient `scene: <nom>` afin d’éviter une traduction accidentelle ou un état réservé Home Assistant. L’attribut `scene_name` conserve toujours le nom exact.

Couper l’éclairage automatique conserve les réglages et l’état courant des lampes. Cela suspend la présence, les scènes conditionnelles, les ajustements naturels et les extinctions automatiques. Les commandes explicites restent utilisables. Le choix de lumière naturelle est conservé pour une réactivation ultérieure.

## 5. Présence et luminosité ambiante

### Présence

Chaque pièce peut sélectionner une entité de présence : détecteur de mouvement, détecteur de présence ou entité personnalisée. Les états signifiant « présent » sont configurables.

- La présence peut déclencher l’allumage si la luminosité le permet.
- Une baisse de luminosité peut déclencher l’allumage alors que la présence est déjà établie.
- L’absence entraîne une extinction après une durée configurable par pièce.
- Une nouvelle présence avant l’échéance annule le compte à rebours.
- Sans source de présence, Halo ne prend aucune décision d’allumage ou d’extinction fondée sur la présence.

Ces décisions sont soumises au mode automatique, aux pauses et à la priorité des scènes décrites plus bas.

### Rallumage rapide après une perte de présence

**Implémenté et testé localement ; validation matérielle et déploiement domestique non réalisés pour cet ajout.** Une fenêtre globale, initialement de **30 secondes**, évite qu’une mesure lumineuse encore élevée après l’extinction retarde le retour des lumières. Elle ne concerne que les pièces dont l’extinction sur forte luminosité est désactivée. Une durée de **0 seconde** désactive cette protection.

La fenêtre commence au début d’une extinction commandée par Halo **pour absence**, si au moins une lampe est encore allumée. Les réévaluations ne la prolongent pas. Un véritable passage **absent → présent**, selon les états configurés, strictement avant son expiration déclenche un seul rallumage sans attendre la mesure lumineuse. Une mise à jour d’attributs ou un passage d’un état inconnu/indisponible vers « présent » ne constitue pas ce retour. La mesure et la mémoire d’hystérésis ne sont pas remplacées par une valeur artificielle.

Halo utilise l’ambiance normalement applicable : scène prioritaire, sinon ambiance de base et profils naturels. La transition est toujours celle de l’**allumage habituel**, avec l’éventuelle valeur propre à la pièce, jamais celle de baisse de luminosité. Le rallumage est envoyé même pendant le fondu d’extinction, si les lampes annoncent encore un état allumé ; les extinctions encore en attente sont invalidées. La publication lumineuse ultérieure ne provoque pas un second allumage progressif.

Cette fenêtre ne s’ouvre pas après une extinction manuelle, une extinction de scène ou une extinction sur luminosité. Elle respecte le mode automatique, les pauses et la suspension d’édition. Une pause encore active empêche ce rallumage : le retour ne la termine que si l’absence continue a atteint la durée minimale décrite dans la section suivante. Une nouvelle intervention manuelle conserve sa priorité et annule la fenêtre, comme l’édition, la désactivation ou une reconfiguration. La fenêtre est consommée après reprise et reste uniquement en mémoire : un redémarrage ne la restaure pas.

Le réglage global `presence_return_window` est un nombre fini obligatoire entre **0 et 604 800 secondes**. Les anciennes configurations sans ce champ reçoivent **30 secondes** ; toute valeur explicitement enregistrée, notamment zéro, est conservée.

### Luminosité et hystérésis

Le capteur de luminosité est facultatif. Lorsqu’il est configuré, l’utilisateur renseigne un seuil fixe et une hystérésis. Le dashboard affiche les seuils effectifs bas et haut ; entre ces seuils, la décision précédente est conservée. Dans l’implémentation, le seuil bas est le seuil renseigné et le seuil haut est ce seuil augmenté de l’hystérésis : la pièce est sombre sous le seuil bas et suffisamment lumineuse à partir du seuil haut.

L’unité affichée pour le seuil, l’hystérésis et les seuils effectifs provient de l’attribut `unit_of_measurement` du capteur sélectionné : par exemple `lx` ou `%`. Aucune unité n’est inventée si elle manque. Les comparaisons utilisent les valeurs natives du capteur ; sélectionner un autre capteur ne convertit pas automatiquement les seuils existants.

Chaque pièce choisit si la luminosité :

- Autorise seulement l’allumage automatique.
- Autorise aussi l’extinction lorsque la luminosité devient suffisante, après une temporisation configurable.

Une mesure indisponible n’est jamais assimilée à zéro. L’extinction sur luminosité doit être validée avec un capteur susceptible de mesurer la lumière produite par les lampes elles-mêmes ; l’hystérésis seule ne doit pas être présentée comme une garantie contre toutes les oscillations.

## 6. Commandes manuelles, pause et reprise

### Un mécanisme commun à toute la pièce

Les modifications manuelles de luminosité, de couleur, les allumages, les extinctions et les lancements explicites de scènes déclenchent une même pause pour toute la pièce.

Pendant la pause, les scènes conditionnelles et les ajustements naturels cessent de modifier les lampes. Le mécanisme empêche notamment un rallumage automatique immédiat après une extinction manuelle.

Un réglage **par pièce**, « Autoriser l’extinction automatique pendant une pause manuelle », détermine si l’absence et la forte luminosité peuvent encore éteindre la pièce. Il est **activé par défaut**. L’extinction sur forte luminosité reste également soumise à sa propre activation dans la configuration de la pièce.

Cette option ne réactive pas les extinctions lorsque l’interrupteur général d’automatisation est désactivé. La suspension d’édition en direct est distincte et arrête toujours tous les automatismes de la pièce.

### Fin de la pause

La pause se termine au premier des événements suivants :

1. Expiration du délai configurable de pause manuelle.
2. Retour dans la pièce après une absence confirmée.
3. Action sur le bouton de reprise.

**Protection contre les pertes brèves de présence : implémentée et testée localement, sans validation matérielle ni déploiement domestique pour cet ajout.** La même durée globale `presence_return_window`, initialement de **30 secondes**, fixe un minimum d’absence continue avant qu’un retour puisse terminer une pause manuelle. La durée requise est la plus grande entre le délai d’absence propre à la pièce et cette durée globale : **`max(absence_delay, presence_return_window)`**. La pause est réinitialisée au **retour de présence**, jamais simplement parce que cette durée est écoulée pendant l’absence.

Cette protection de la pause concerne **toutes les pièces**, indépendamment du choix d’extinction sur forte luminosité. Un état de présence inconnu ou indisponible interrompt la continuité de l’absence ; il ne compte pas dans sa durée. Un retour trop tôt conserve la pause, y compris le nom d’une scène lancée explicitement. L’expiration propre de la pause et le bouton de reprise gardent leur fonctionnement habituel.

Avec une durée globale de **0**, seule cette durée minimale supplémentaire disparaît ; le délai d’absence de la pièce reste applicable. Ce réglage ne retarde pas l’extinction automatique, qui conserve son délai d’absence. La fenêtre de rallumage rapide garde son propre point de départ à l’envoi de l’extinction et reste soumise à une pause encore active ; aucune restauration automatique d’une ambiance manuelle n’est ajoutée.

Une extinction manuelle déclenche la pause ; elle ne l’annule pas immédiatement. Les commandes et les retours d’état produits par Halo, y compris pendant une transition, ne doivent pas être interprétés comme une intervention manuelle.

Les pauses et leur échéance sont conservées pour survivre à un redémarrage. Une réévaluation respecte toujours les modes actifs de la pièce.

## 7. Ambiance de base

Chaque pièce peut enregistrer une ambiance de référence, avec des réglages par lampe. Elle sert de base lorsqu’aucune scène conditionnelle ne s’applique. Les profils naturels actifs remplacent les paramètres de luminosité et de température concernés.

Pour une lampe sans réglage enregistré, Halo envoie simplement une commande d’allumage, accompagnée uniquement de la transition applicable éventuelle. La lampe utilise alors ses propres réglages internes ; Halo n’invente pas une luminosité ou une couleur de base.

## 8. Profils de lumière naturelle

### Soleil et courbes

L’utilisateur sélectionne globalement une entité soleil fournissant son élévation. Les profils naturels sont nommés, réutilisables et indépendants des pièces.

Chaque profil définit deux courbes indépendantes :

- Une courbe de température de blanc : deux hauteurs solaires et les valeurs associées en kelvins.
- Une courbe de luminosité : deux hauteurs solaires et les valeurs associées en pourcentage.

À la création d’un profil, la luminosité va de **40 % à −20°** à **100 % à 20°**, et la température de **2 000 K à 0°** à **5 500 K à 20°**. Ces valeurs reprennent celles de l’ancien script avec le minimum de luminosité arrondi à 40 %. Les deux courbes sont linéaires et le matin/soir reste lié par défaut ; ces nouveaux défauts ne modifient aucun profil déjà enregistré.

Chaque courbe propose un **type de courbe** :

- **Linéaire**, sélectionné par défaut : la valeur évolue à rythme constant par degré de hauteur solaire.
- **Accélération et décélération progressives** : la valeur démarre doucement, accélère au milieu puis ralentit à l’approche de la hauteur haute. La courbe en S rejoint les deux plateaux sans rupture de pente. Ce comportement remplace l’accélération quadratique initiale, conformément au retour sur le graphique.

Le choix est indépendant pour la luminosité et la température du blanc. Il concerne la relation entre hauteur solaire et valeur cible, pas la durée d’une transition de lampe. Au soleil descendant, la même courbe se parcourt dans l’autre sens. Les valeurs restent aux limites au-delà des deux hauteurs configurées. Les hauteurs solaires conservent leur précision décimale. Les paramètres incohérents empêchant le calcul doivent être signalés lors de la configuration. Les profils déjà enregistrés sans type de courbe conservent leur comportement linéaire.

La case **« Lier le matin et le soir »** est cochée par défaut. Elle partage les courbes entre soleil montant et descendant. Décochée, elle permet de régler les deux périodes distinctement. L’éditeur présente un aperçu graphique des courbes.

Le type de courbe suit ce même fonctionnement : partagé lorsque matin et soir sont liés, configurable séparément pour chaque période lorsqu’ils sont dissociés. L’aperçu représente immédiatement le type sélectionné et les valeurs calculées par le moteur.

Les profils déjà réglés sur l’ancienne accélération progressive adoptent cette correction en S ; les profils linéaires et ceux sans type explicite restent linéaires. La normalisation se fait en mémoire et ne déclenche pas à elle seule une écriture ; une sauvegarde ultérieure de configuration ou d’état d’exécution conserve le nouvel identifiant.

Les graduations horizontales de cet aperçu correspondent aux deux hauteurs solaires configurées, à leur position exacte sur la courbe, et non aux extrémités des marges du graphique. Les plateaux et les valeurs décimales restent visibles.

### Associations dans les pièces

Une pièce peut associer des groupes de lampes différents à plusieurs profils : par exemple, une lumière très chaude pour un groupe et moins chaude pour un autre.

- Chaque association sélectionne son profil et ses lampes compatibles, au minimum variables en luminosité.
- Chaque association peut appliquer une correction relative de luminosité en pourcentage, par exemple −30 %, sans modifier le profil partagé.
- Le résultat est limité aux capacités de chaque lampe.
- Les mises à jour naturelles ajustent les lampes allumées sans rallumer celles qui sont éteintes.
- Une scène conditionnelle sélectionnée prend le pas sur la lumière naturelle.

### Capacités des lampes

| Capacité | Gestion de l’éclairage | Application du profil naturel |
| --- | --- | --- |
| Marche/arrêt | Commande de pièce et scènes. | Pas d’affectation naturelle. |
| Variation seule | Marche/arrêt et luminosité. | Luminosité uniquement. |
| Variation et température du blanc | Marche/arrêt, luminosité et température. | Luminosité et kelvins, bornés aux capacités annoncées. |
| Variation et couleur sans température du blanc | Marche/arrêt, luminosité et couleur. | Luminosité et approximation de la température via la couleur prise en charge. |

Quand une lampe prend en charge nativement la température du blanc, Halo utilise cette capacité. La simulation par couleur sert aux lampes sans cette capacité et ne garantit pas un rendu identique à celui d’une lampe à blanc réglable.

Si le soleil devient indisponible, les ajustements naturels sont suspendus ; aucune valeur artificielle n’est calculée à partir de zéro. Le dashboard signale cette indisponibilité.

## 9. Scènes, conditions et priorités

### Création et conditions

Les scènes sont créées et enregistrées dans Halo. Elles décrivent l’état souhaité des lumières sélectionnées dans leur pièce : marche/arrêt, variation, température du blanc, couleur et effet lorsque la lampe l’expose à Home Assistant.

L’éditeur de conditions propose les états d’entités, seuils numériques, horaires et conditions solaires, combinables avec **ET**, **OU** et **NON**, sans YAML obligatoire.

### Import depuis Home Assistant

**Implémenté ; vérifié dans Home Assistant 2026.10.0 isolé avec des lampes simulées.** Un administrateur peut importer la configuration d’une scène Home Assistant dans une pièce Halo. Une recherche permet de choisir la scène ; le panneau présente les lampes retenues, le nombre d’entités ignorées et un nom modifiable avant confirmation. La copie est ajoutée en dernière position au brouillon de la pièce, sans condition et sans autorisation d’allumage automatique, puis enregistrée ou abandonnée avec la barre habituelle. Son lancement est disponible après enregistrement.

Seuls les identifiants de lampes explicitement sélectionnées dans la pièce sont repris. Les groupes ne sont pas développés et aucune correspondance avec leurs membres n’est déduite. Une scène sans lampe commune est refusée. Les lampes absentes de la scène restent inchangées à son lancement ; elles ne sont pas ajoutées automatiquement lorsqu’on rouvre l’éditeur.

L’import conserve les réglages reproductibles enregistrés dans la source, effets compris. Il ne commande aucune lampe, ne modifie jamais la scène source et ne crée aucune synchronisation ultérieure. La scène Halo possède son propre identifiant.

Le périmètre est celui de l’API de configuration utilisée par l’éditeur Home Assistant : scènes dans `scenes.yaml` avec un identifiant, notamment celles créées depuis son interface. Les scènes temporaires, le YAML placé ailleurs et les scènes directement fournies par d’autres intégrations sont signalés comme non importables lorsque leurs réglages ne sont pas accessibles. Cette API du cœur n’est pas un contrat public garanti stable ; sa compatibilité doit être vérifiée avec la version Home Assistant prise en charge.

### Ordre de priorité

L’ordre visuel définit la priorité. Les scènes peuvent être déplacées et disposent également de boutons monter/descendre.

- La première scène dont les conditions sont remplies est sélectionnée.
- Une seule scène conditionnelle s’applique à la fois.
- Elle prime sur la lumière naturelle.
- Lorsque ses conditions cessent d’être remplies, Halo sélectionne la suivante ou revient au fonctionnement normal, avec l’ambiance de base et les profils naturels applicables.

### Droit de déclencher l’allumage

Chaque scène précise si elle peut déclencher l’allumage :

| Choix | Comportement |
| --- | --- |
| Autorisé | La scène peut allumer et maintenir son ambiance indépendamment de la présence et de la luminosité. |
| Non autorisé | La scène règle l’ambiance lorsque la pièce doit être allumée ; sa condition seule ne provoque pas l’allumage. |

Dans les deux cas, l’exécution conditionnelle respecte la désactivation générale de l’automatisation, la pause manuelle et la suspension d’édition. Allumer une pièce alors qu’une scène est sélectionnée laisse éteintes les lampes que cette scène prévoit éteintes.

Chaque scène est également exposée comme entité `scene` Home Assistant. Son lancement explicite applique son ambiance et déclenche la pause manuelle commune, y compris lorsque les automatismes sont désactivés.

### Règles communes de priorité

| Situation | Effet attendu sur les automatismes |
| --- | --- |
| Édition en direct | Tous les automatismes de la pièce sont suspendus ; l’éditeur contrôle l’aperçu. |
| Automatisation désactivée | Aucun automatisme ne commande les lampes ; les commandes explicites restent utilisables. |
| Pause manuelle | Scènes conditionnelles et lumière naturelle suspendues ; seules les extinctions éventuellement autorisées par pièce restent possibles. |
| Scène sélectionnée autorisée à allumer | Son ambiance prime sur présence, luminosité et lumière naturelle. |
| Scène sélectionnée sans droit d’allumage | Les règles d’allumage déterminent si la pièce doit être éclairée ; la scène détermine son ambiance. |
| Aucune scène sélectionnée | Application des règles normales, de l’ambiance de base et des profils naturels actifs. |

## 10. Édition des scènes en direct

L’utilisateur règle les lampes réelles depuis le dashboard et voit le résultat dans sa pièce. Seules les lampes sélectionnées dans cette pièce sont proposées.

**Implémenté ; vérifié dans Home Assistant local avec des lampes simulées :** chaque lampe apparaît dans une liste Halo recherchable ; un clic ouvre la véritable fenêtre de contrôle Home Assistant, comme dans son éditeur de scènes. L’ouverture utilise l’action publique `more-info` via `hass-action`. Halo n’importe pas les composants privés de cet éditeur et ne copie pas leurs contrôles. HACS assure la distribution, pas la fourniture de ces composants. Les essais sur les équipements du logement restent à effectuer.

À l’enregistrement, le serveur capture les états réels des lampes : état, luminosité native, mode de couleur et valeur correspondante (y compris RGBW/RGBWW et blanc simple), ainsi que l’effet actif. Les représentations de couleur dérivées ne sont pas envoyées simultanément. La garantie porte sur les réglages reproductibles remontés par l’entité `light` ; les informations de capacité, les impulsions temporaires et les fonctions propriétaires non remontées ne constituent pas des paramètres de scène. Une lampe éteinte est restaurée sans rallumage temporaire. Une lampe indisponible conserve son réglage mémorisé s’il existe ; aucune extinction artificielle n’est enregistrée.

L’éditeur propose une inclusion explicite par lampe. Pour une scène existante, seules ses lampes sont incluses au départ ; une nouvelle scène manuelle inclut initialement toutes les lampes de la pièce. Seules les lampes incluses sont capturées à l’enregistrement. Une lampe exclue ne reçoit aucune commande de la scène.

- Toute automatisation de la pièce est temporairement suspendue, y compris l’extinction sur absence ou luminosité.
- L’état initial est mémorisé.
- Une seule session d’édition peut contrôler une pièce à la fois.
- Les commandes d’aperçu ne sont pas interprétées comme une nouvelle pause manuelle.
- **Enregistrer** conserve la scène et rétablit le fonctionnement correspondant aux modes et conditions actuels.
- **Annuler** restaure l’état initial puis libère la suspension.
- Une fermeture ou une perte de connexion libère automatiquement la session après expiration, pour éviter une suspension permanente.
- Si l’automatisation était désactivée avant l’édition, elle le reste.

L’état d’édition, la suspension et les éventuelles indisponibilités sont visibles dans le dashboard.

La première implémentation utilise une expiration de **120 secondes** sans renouvellement de la connexion propriétaire. L’enregistrement final verrouille la session pendant la sauvegarde, afin qu’une expiration concurrente ne provoque pas une restauration après un enregistrement réussi.

## 11. Transitions

### Cinq catégories

| Catégorie | Cas d’utilisation |
| --- | --- |
| Allumage habituel | Allumage par présence ou commande d’allumage. |
| Baisse de luminosité | Allumage parce que la luminosité baisse dans une pièce déjà occupée. |
| Lumière naturelle | Ajustement des valeurs d’un profil naturel. |
| Scène | Activation, changement ou sortie d’une scène. |
| Extinction | Extinction de la pièce. |

Les durées sont exprimées en secondes. Les cinq valeurs sont configurables globalement. Pour chaque catégorie, chaque pièce choisit explicitement :

1. **Hériter** de la valeur globale.
2. **Définir une durée** locale.
3. **Ne demander aucune transition**.

Un champ vide en configuration explicite signifie que Halo omet le paramètre de transition. Il ne signifie pas implicitement « hériter ». Une valeur `0` demande une transition immédiate lorsque la lampe la prend en charge. Une lampe sans prise en charge ne reçoit pas le paramètre. L’absence de paramètre laisse s’appliquer le comportement propre à la lampe.

### Choix selon le déclencheur

La catégorie dépend de la cause de la commande :

- Une présence ou une commande d’allumage utilise l’allumage habituel, même si une scène est sélectionnée.
- Une baisse de luminosité dans une pièce occupée utilise la durée dédiée.
- Une scène provoquant elle-même l’allumage utilise la durée de scène.
- Les ajustements naturels utilisent leur durée dédiée.
- Une extinction de la pièce utilise la durée d’extinction.

Une nouvelle commande remplace les anciennes intentions encore en attente. Une transition ne doit ni réappliquer une ancienne ambiance après une nouvelle commande, ni créer une fausse détection d’intervention manuelle.

## 12. Architecture retenue

**Architecture actée et implémentée dans cette première version de développement.** Les contrats techniques figurent dans [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

- Un moteur par pièce fonctionne dans l’intégration Python Home Assistant. Il reste actif indépendamment de l’ouverture du panneau.
- Le panneau embarqué est développé en TypeScript avec Lit. Les ressources distribuables accompagnent l’intégration, sans installation séparée.
- Des commandes WebSocket authentifiées relient le panneau au moteur ; les droits d’administration sont validés côté serveur.
- Les registres Home Assistant fournissent les pièces, entités et capacités utiles.
- Le stockage de configuration Home Assistant est versionné. Les identifiants de pièces, profils et scènes sont stables.
- Les abonnements et temporisations sont libérés au déchargement.
- Les pauses manuelles sont conservées avec leur échéance pour survivre à un redémarrage.
- Les indisponibilités des entités sont distinguées des valeurs valides et présentées à l’utilisateur.

Les conventions de développement existantes restent applicables. Les changements sont couverts par des tests locaux ; l’installation et les essais réels restent un jalon distinct.

## 13. Valeurs initiales

Ces valeurs sont les valeurs par défaut retenues et appliquées dans la première implémentation.

| Paramètre | Valeur initiale |
| --- | --- |
| Automatismes d’une pièce nouvellement configurée | Désactivés jusqu’à leur activation. |
| Transitions globales | Allumage habituel : 0 s ; baisse de luminosité : 10 s ; ajustement naturel : 60 s ; scène : 10 s ; extinction : 2 s. |
| Transitions par pièce | Héritage des valeurs globales. |
| Courbes matin/soir d’un profil | Liées. |
| Luminosité d’un nouveau profil | 40 % à −20° ; 100 % à 20° ; courbe linéaire. |
| Température d’un nouveau profil | 2 000 K à 0° ; 5 500 K à 20° ; courbe linéaire. |
| Extinction sur forte luminosité | Désactivée. |
| Extinction automatique pendant la pause manuelle | Autorisée ; configurable par pièce. |
| Délai d’absence | 0 seconde, modifiable. |
| Protection globale contre les pertes de présence | 30 secondes, modifiable ; 0 désactive le rallumage rapide et le minimum supplémentaire de protection de la pause, sans changer le délai d’absence. |
| Durée de pause manuelle | 120 minutes, modifiable. |
| Confirmation de forte luminosité avant extinction | 30 secondes, modifiable. |
| Seuil lumineux | À renseigner lorsqu’un capteur est configuré. |
| Hystérésis | Zéro, modifiable. |
| Langue de référence et de repli | Anglais. |
| Autre langue fournie | Français, pour `fr` et ses variantes. |

Ces valeurs remplacent les choix initiaux (absence 120 secondes, pause 15 minutes et transitions globales vides), à la demande du 9 octobre 2026. Elles s’appliquent aux nouvelles configurations ; les réglages déjà enregistrés, y compris `0` et les transitions vides (`null`), sont conservés. Les pièces continuent d’hériter des transitions globales par défaut. Le champ vide reste un choix explicite valide pour omettre une transition. La durée globale de protection contre les pertes de présence est aussi ajoutée à 30 secondes aux anciennes configurations qui ne contiennent pas encore ce champ.

## 14. Scénarios d’acceptation

**Ces scénarios restent la référence d’acceptation complète.** Les tests automatisés couvrent notamment le moteur, les entités, la persistance, les droits, la concurrence et les langues. Leur réussite locale ne vaut pas validation matérielle ou validation de tous les parcours dans une instance Home Assistant ; ces dernières restent à réaliser.

Pour la refonte du 9 octobre 2026, les **52 tests frontend** (43 du panneau, 9 du modèle) et le contrôle TypeScript réussissent. Les aperçus ont été examinés à 390 et 1 436 pixels de large, en clair, sombre et avec un thème personnalisé et une police à 125 %. Dans Home Assistant 2026.10.0 isolé, l’ouverture d’une scène partielle à deux lampes sur quatre, la fenêtre native avec l’effet « Candle », l’annulation libérant la session et l’import de deux entités retenues/deux ignorées jusqu’au brouillon puis à son abandon ont été vérifiés sans erreur console. Les lampes de ces essais sont simulées. Les preuves détaillées restent dans [le guide de développement](docs/DEVELOPMENT.md).

| Référence | Scénario | Résultat attendu |
| --- | --- | --- |
| A01 | Ajouter Halo et essayer une seconde installation. | Une seule entrée ; le panneau apparaît après la première installation. |
| A02 | Utiliser le panneau avec un utilisateur ordinaire puis un administrateur. | Pilotage accessible ; écritures de configuration réservées aux administrateurs côté serveur. |
| A03 | Configurer une pièce, rechercher des lumières et essayer des affectations incompatibles. | Sélection explicite ; priorité visuelle aux lumières de la pièce ; exclusion des lumières Halo, des doublons de pièce et des doubles profils. |
| A04 | Renommer une pièce et changer l’état ou la disponibilité de ses lampes. | Appareil conservé ; état agrégé réel ; indisponible lorsque toutes les lampes le sont. |
| A05 | Détecter une présence, une absence puis un retour avant l’échéance. | Allumage si autorisé ; extinction retardée ; compte à rebours annulé au retour. |
| A06 | Faire baisser la luminosité pendant une présence déjà établie ; osciller entre les seuils. | Allumage avec la bonne transition ; décision conservée dans la bande d’hystérésis. |
| A07 | Activer puis désactiver l’extinction sur forte luminosité. | Respect du choix par pièce et de la temporisation ; essai avec un capteur influencé par les lampes. |
| A08 | Modifier une lampe ou éteindre manuellement la pièce. | Pause commune à toute la pièce ; aucune réapplication automatique immédiate. |
| A09 | Tester les deux choix d’extinction pendant une pause manuelle. | Absence et forte luminosité n’éteignent que lorsque l’option et les fonctions correspondantes l’autorisent. |
| A10 | Attendre la fin de pause, revenir après une absence confirmée ou utiliser le bouton. | Reprise à la première condition remplie ; bouton réactivant l’automatisation. |
| A11 | Désactiver l’automatisation ; commander explicitement une lumière ou une scène. | Automatismes suspendus, état et réglages conservés ; commandes explicites toujours possibles. |
| A12 | Appliquer plusieurs profils dans une pièce, avec correction de luminosité. | Groupes distincts, profils partagés inchangés et résultats bornés aux capacités. |
| A13 | Tester les bornes solaires, leurs décimales et les courbes liées ou séparées. | Interpolation correcte, valeurs limites respectées et distinction matin/soir conforme au réglage. |
| A14 | Tester les quatre familles de lampes et éteindre un membre d’un groupe naturel. | Commandes compatibles ; température native préférée ; approximation couleur adaptée ; aucune réactivation par une mise à jour naturelle. |
| A15 | Rendre vraies deux conditions de scènes et changer leur ordre. | Une seule scène appliquée : la première admissible dans l’ordre affiché. |
| A16 | Faire cesser une condition ou appliquer une scène autorisée à allumer. | Passage à la suivante ou au fonctionnement normal ; priorité sur présence/luminosité uniquement lorsque le droit d’allumage est accordé. |
| A17 | Allumer la pièce dans une scène laissant certaines lampes éteintes ; lancer une entité scène. | États prévus par la scène respectés ; lancement explicite déclenchant la pause manuelle. |
| A18 | Utiliser l’ambiance de base sans scène ni profil naturel applicable, puis retirer le réglage d’une lampe. | Réglages enregistrés appliqués ; sinon commande d’allumage sans luminosité ni couleur imposée. |
| A19 | Éditer une scène en direct, enregistrer puis annuler une autre édition. | Pièce suspendue pendant l’aperçu ; reprise selon les modes après sauvegarde ; restauration initiale après annulation. |
| A20 | Fermer l’éditeur, perdre la connexion ou ouvrir une deuxième session. | Expiration libérant la suspension ; une seule session contrôlant la pièce ; mode automatique antérieur respecté. |
| A21 | Tester chaque catégorie de transition, l’héritage, la durée locale, le champ vide et `0`. | Bonne catégorie selon le déclencheur ; distinction héritage/absence/zéro ; paramètre omis pour une lampe incompatible. |
| A22 | Envoyer une nouvelle commande pendant une transition. | Dernière intention respectée ; aucune ancienne commande réappliquée ni fausse pause manuelle. |
| A23 | Rendre une source de présence, de luminosité, de soleil ou une lampe indisponible, puis la rétablir. | Indisponibilité explicite ; aucune mesure remplacée par zéro ; récupération vérifiée. |
| A24 | Fermer le panneau, recharger l’intégration et redémarrer Home Assistant pendant une pause. | Moteur indépendant du panneau ; ressources libérées ; configuration, identifiants et échéance de pause conservés. |
| A25 | Utiliser le français, ses variantes, l’anglais et une langue non prise en charge. | Français pour les variantes françaises ; anglais autrement ; noms personnalisés et identifiants inchangés. |
| A26 | Rechercher par nom ou identifiant dans les sélecteurs d’entités et listes de lumières, au clavier et à la souris. | Filtrage immédiat ; sélection conservée si la recherche est abandonnée ; entités indisponibles identifiables. |
| A27 | Afficher une entité de groupe, une lampe membre et une lampe sans groupe connu. | Nature et appartenances connues explicites ; aucune information inaccessible divulguée. |
| A28 | Sélectionner des capteurs en `lx`, en `%`, puis sans unité. | Unités adaptées sur seuil et hystérésis ; aucune conversion implicite des valeurs. |
| A29 | Créer un profil naturel et une scène via une adresse Home Assistant locale en HTTP. | Création et sauvegarde possibles sans dépendre de `crypto.randomUUID`, réservé aux contextes sécurisés. |
| A30 | Créer une configuration puis recharger une ancienne configuration. | Nouveaux défauts appliqués à la création ; durées et transitions déjà enregistrées conservées. |
| A31 | Modifier un réglage puis faire défiler une longue page sur ordinateur et mobile. | Barre d’enregistrement visible au bas de la fenêtre ; derniers champs accessibles sans recouvrement. |
| A32 | Afficher des courbes avec seuils décimaux, proches, négatifs ou aux limites. | Graduations aux hauteurs saisies et aux positions exactes ; plateaux conservés et libellés lisibles. |
| A33 | Afficher les transitions avec des titres de longueurs différentes, globalement et par pièce. | Champs alignés dans chaque rangée, y compris après un changement de largeur. |
| A34 | Afficher des groupes Philips Hue v1/v2, dont un groupe sans membres exposés. | Nature du groupe reconnue ; seuls les membres connus et autorisés sont affichés. |
| A35 | Choisir le type de chaque courbe, enregistrer et recharger ; ouvrir un ancien profil sans type. | Choix indépendants conservés, ancien profil linéaire, valeur inconnue rejetée par le serveur. |
| A36 | Comparer linéaire et progression en S aux seuils, aux quarts et à mi-parcours, sur des courbes croissantes ou décroissantes. | Valeurs limites inchangées ; progression en S de 15,625 %, 50 % puis 84,375 % aux quarts du parcours solaire, avec ralentissement aux deux extrémités ; aperçu et moteur concordants. |
| A37 | Cliquer sur une lampe pendant l’édition de scène et choisir un effet dans Home Assistant. | Véritable fenêtre native ouverte par l’action publique ; état et effet remontés visibles dans Halo ; automatisation suspendue. |
| A38 | Enregistrer puis recharger et relancer une scène avec effet, couleurs RGBW/RGBWW ou blanc simple. | Capture serveur des valeurs actives ; effet et canaux blancs conservés ; aucune couleur dérivée concurrente envoyée. |
| A39 | Annuler ou laisser expirer une édition native ; rendre une lampe indisponible pendant la sauvegarde. | État initial reproductible restauré, effets compris ; lampe éteinte sans rallumage temporaire ; réglages connus préservés en cas d’indisponibilité. |
| A40 | Importer une scène Home Assistant comportant deux lampes de la pièce, une lampe extérieure et un autre domaine. | Deux lampes retenues, deux entités ignorées ; nom modifiable et copie indépendante, sans activation de la source ni commande pendant l’import et sa sauvegarde. |
| A41 | Lancer une scène importée, puis la rouvrir et l’enregistrer sans changer les inclusions. | Seules les lampes incluses sont commandées et capturées ; les autres restent inchangées et ne sont pas ajoutées à la scène. |
| A42 | Importer des états simples, des booléens YAML, des effets et plusieurs représentations de couleur. | Valeurs normalisées selon le mode actif ou la priorité native ; effets et canaux blancs conservés ; aucun attribut descriptif envoyé aux lampes. |
| A43 | Importer sans correspondance, avec une source inaccessible ou invalide ; annuler ou provoquer un conflit de sauvegarde. | Erreur explicite sans commande ni copie enregistrée ; droits serveur respectés et brouillon préservé. |
| A44 | Rechercher une pièce, la piloter depuis la liste puis ouvrir ses sous-vues sur ordinateur et mobile. | Liste/détail adaptée à l’écran ; commandes et états accessibles ; cinq onglets administrateur, pilotage seul pour les autres utilisateurs. |
| A45 | Modifier plusieurs sous-vues ou profils avant une sauvegarde ; saisir une valeur invalide puis naviguer ou abandonner. | Brouillon conservé ; navigation bloquée sur une erreur révélée et focalisée ; abandon restaurant les valeurs enregistrées. |
| A46 | Parcourir les onglets au clavier puis importer ou éditer une scène. | Flèches, Début et Fin déplacent l’onglet actif et le focus ; navigation bloquée pendant l’édition réelle ; retour au pilotage et focus approprié. |
| A47 | Changer le thème Home Assistant, agrandir la police et activer la réduction des mouvements. | Couleurs, typographie et contrôles suivent le thème ; aucune palette Halo imposée ; contenu accessible et animations supprimées lorsque demandé. |
| A48 | Observer le capteur d’état pendant un allumage naturel, une scène conditionnelle ou explicite, une intervention manuelle, une édition, une extinction et une indisponibilité ; renommer et recharger la pièce. | État conforme aux priorités ci-dessus, nom de scène conservé avec préfixe pour les noms réservés, attributs stables, traductions anglaises/françaises des états fixes, mises à jour sans panneau ouvert et identité conservée. |
| A49 | Éteindre pour absence, puis revenir avant la fin de la fenêtre alors que la luminosité est encore haute, y compris pendant le fondu et avec plusieurs extinctions en attente. | Rallumage unique avec l’ambiance applicable et la transition d’allumage habituel ; anciennes intentions d’extinction invalidées, sans attendre ni falsifier le capteur lumineux. |
| A50 | Tester zéro, l’expiration exacte, une absence longue, une première entrée lumineuse, les états personnalisés et le retour de disponibilité ; intervenir manuellement, éditer, désactiver ou reconfigurer. | Protection uniquement dans sa fenêtre et pour un vrai retour après extinction pour absence ; aucun contournement des pauses, de l’édition ou des pièces autorisant l’extinction sur luminosité ; fenêtre annulée dans les cas prévus et non restaurée au redémarrage. |
| A51 | Modifier la fenêtre globale, saisir une valeur invalide, sauvegarder/recharger et ouvrir une ancienne configuration. | Valeur finie de 0 à 604 800 secondes exigée ; droits, brouillon et révisions respectés ; valeur explicite conservée, défaut de 30 secondes si champ absent ; libellés et aide anglais/français. |
| A52 | Pendant une pause manuelle, revenir avant, à et après `max(absence_delay, presence_return_window)`, avec puis sans extinction sur forte luminosité. | Retour trop tôt sans réinitialisation ; retour après une absence continue suffisante terminant la pause, sans réinitialisation pendant l’absence elle-même ; expiration propre et bouton de reprise inchangés. |
| A53 | Régler la protection globale à zéro, interrompre une absence par une indisponibilité et combiner pause avec extinction pour absence puis retour rapide. | Délai d’absence local conservé à zéro global ; indisponibilité interrompant la continuité ; extinction au délai local habituel ; une pause encore active bloque le rallumage rapide sans restaurer artificiellement l’ambiance manuelle. |

Pour chaque scénario réalisé, consigner son résultat, la version examinée et le périmètre : test automatisé, essai d’interface ou essai sur des lumières réelles. Une fonctionnalité implémentée n’est pas automatiquement validée dans Home Assistant.

## 15. Suivi, décisions et publication

Chaque évolution met à jour dans la même tâche la spécification, le statut d’implémentation et les preuves de vérification. Les idées nouvelles restent explicitement proposées jusqu’à leur adoption. Les règles d’interface sont reportées dans `DESIGN.md` et les capacités livrées dans le README.

Le choix des contrôles natifs de scène repose sur les [mécanismes officiels vérifiés et leurs limites](docs/ARCHITECTURE.md#contrôles-natifs-des-lampes-dans-les-scènes). Aucun détournement de composant interne n’est retenu.

| Date | Décision | Conséquence |
| --- | --- | --- |
| 9 octobre 2026 | Initialiser Halo avec une identité de lotus et une structure adaptée à Home Assistant et HACS. | Le socle est préparé avant les fonctions d’éclairage. |
| 9 octobre 2026 | Reporter la disponibilité HACS à la fin du projet. | La publication reste un jalon futur. |
| 9 octobre 2026 | Maintenir `PROJET.md`, `DESIGN.md` et `README.md` en temps réel. | Chaque évolution est documentée dans la même tâche. |
| 9 octobre 2026 | Adopter le panneau unique, les appareils par pièce et les règles d’automatisation décrites ici. | Spécification actée ; fonctionnalités à développer. |
| 9 octobre 2026 | Unifier la pause manuelle et rendre son extinction automatique configurable par pièce. | Le réglage est activé par défaut ; scènes et ajustements naturels restent suspendus pendant la pause. |
| 9 octobre 2026 | Adopter les profils réutilisables, les scènes prioritaires éditables en direct et les transitions globales avec réglages locaux. | Configuration centralisée dans le futur panneau. |
| 9 octobre 2026 | Utiliser l’anglais comme référence, avec français selon la langue de l’interface Home Assistant. | Localisation complète à développer et catalogues extensibles. |
| 9 octobre 2026 | Lancer le développement du cahier des charges. | Première implémentation du moteur, des entités et du panneau ; validation locale et essais matériels distingués. |
| 9 octobre 2026 | Préciser les groupes, rendre les entités recherchables, suivre les unités des capteurs et ajuster les valeurs initiales après les premiers retours du panneau. | Nouvelles règles décrites ci-dessus ; conservation des réglages existants et création de profils/scènes compatible HTTP local. |
| 9 octobre 2026 | Refaire le panneau avec pilotage prioritaire, liste/détail et développement direct, en suivant le thème Home Assistant. | Refonte compacte implémentée et vérifiée localement, sans suppression d’option métier ; cinq onglets par pièce et profils dans une vue dédiée. Aucun déploiement domestique ni publication HACS n’en découle. |
| 9 octobre 2026 | Ajouter une fenêtre globale de rallumage après une extinction pour absence, initialement de 30 secondes. | Un retour rapide ignore ponctuellement la luminosité et utilise la transition de présence, uniquement lorsque l’extinction sur luminosité est désactivée ; zéro désactive la protection. |
| 9 octobre 2026 | Réutiliser la durée globale pour protéger le mode manuel des pertes brèves de présence. | Le retour ne termine la pause qu’après une absence continue d’au moins le maximum entre délai local et durée globale, pour toutes les pièces ; ni l’extinction automatique ni l’expiration propre de pause ne sont retardées. |

Le développement et les essais précèdent toute publication. La release et la demande d’inclusion HACS suivent ensuite la [procédure documentée](docs/HACS.md). Aucun référencement n’est déclenché par la rédaction de ce cahier des charges.
