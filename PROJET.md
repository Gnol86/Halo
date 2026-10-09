# Halo — Projet et fonctionnalités

Dernière mise à jour : **9 octobre 2026**.

Ce document est le cahier des charges de Halo : objectifs, fonctionnalités, interactions, architecture et critères de validation. Les comportements ci-dessous sont actés. Une première implémentation de développement existe maintenant ; les statuts et limites de vérification sont précisés ci-dessous. La spécification reste la référence du résultat attendu, et ne prouve pas à elle seule son fonctionnement sur du matériel réel.

Ce document, [DESIGN.md](DESIGN.md) et [README.md](README.md) doivent rester à jour en temps réel, conformément à [AGENTS.md](AGENTS.md). `DESIGN.md` détaille l’organisation et les interactions du dashboard ; ses choix esthétiques restent à définir. Le README présente les capacités effectivement disponibles. Les jalons se trouvent dans [docs/ROADMAP.md](docs/ROADMAP.md).

## 1. Vision et état du projet

Halo est une intégration personnalisée Home Assistant destinée à gérer toutes les lumières du logement, avec une configuration simple et centralisée. Son domaine est `halo`, son identité est une fleur de lotus et une seule installation couvre l’ensemble du logement.

Le socle initial est implémenté : ajout depuis l’interface Home Assistant, entrée de configuration unique, chargement/déchargement/rechargement, textes de configuration anglais et français, icônes locales, tests et workflows préparés. Les vérifications historiques et leurs limites sont consignées dans [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

Limite vérifiée le 9 octobre 2026 : HACS 2.0.5 ne charge pas les icônes embarquées pour sa liste de dépôts. L’image du README utilise une URL absolue GitHub ; les ressources `brand/` restent celles prévues pour Home Assistant. Le [diagnostic des deux emplacements](docs/HACS.md#affichage-du-lotus) distingue cette limite externe de la correction du README. Le référencement par défaut reste un jalon final.

**Une première implémentation du panneau et du moteur d’éclairage est disponible dans le dépôt.** Les tests locaux utilisent Home Assistant avec des lampes simulées ; les essais matériels et la validation finale du dashboard dans une instance Home Assistant restent à effectuer. Les résultats sont consignés dans [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

| Ensemble | Statut actuel |
| --- | --- |
| Socle d’intégration et configuration unique | Implémenté ; vérifications initiales décrites dans la documentation de développement. |
| Panneau, configuration des pièces et appareils | Première implémentation ; tests de cycle de vie, API et appareils locaux. |
| Présence, luminosité, pause manuelle et reprise | Implémenté ; tests avec capteurs et lampes simulés. |
| Ambiance de base et profils naturels | Implémenté ; calculs et adaptation aux capacités testés localement. |
| Scènes, conditions, priorités et édition en direct | Implémenté ; tests locaux des priorités, sessions et restaurations. |
| Transitions globales et par pièce | Implémenté ; paramètres et concurrence testés, comportement matériel à vérifier. |
| Localisation complète et sélection de langue du panneau | Catalogues anglais/français et sélection de langue implémentés ; tests locaux. |
| Direction esthétique du dashboard | À définir dans `DESIGN.md`. |
| Publication et référencement HACS | Jalon final, après développement et validation. |

## 2. Installation et panneau Halo

### Une seule intégration, toute la configuration dans le panneau

L’utilisateur ajoute Halo une seule fois dans Home Assistant. L’intégration ajoute automatiquement un panneau **Halo** dans la barre latérale, sans configuration YAML ni installation séparée de carte. Toute la configuration fonctionnelle se fait dans ce panneau.

Home Assistant fournit un mécanisme de panneau personnalisé pour cette interface. [Documentation officielle](https://developers.home-assistant.io/docs/frontend/custom-ui/creating-custom-panels/).

Le panneau présente :

- Les pièces récupérées depuis Home Assistant, en distinguant les pièces configurées dans Halo des autres.
- Une page par pièce : lumières, automatisation, profils naturels, ambiance de base, scènes et transitions.
- Une section globale : profils naturels, entité soleil et transitions par défaut.
- L’état explicite de chaque pièce : scène sélectionnée, lumière naturelle, pause manuelle, absence, luminosité suffisante ou donnée indisponible.

La fermeture du panneau n’interrompt pas les automatismes.

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

Les pièces proviennent du registre Home Assistant. L’utilisateur choisit explicitement les entités `light` gérées dans chacune d’elles. Le sélecteur présente d’abord les lumières rattachées à la pièce dans Home Assistant et permet ensuite de rechercher les autres.

- Une lampe appartient à une seule pièce Halo.
- Dans cette pièce, elle appartient au maximum à une association de profil naturel.
- Les lumières générées par Halo sont exclues des sélections, afin d’éviter les boucles de commande.
- Une nouvelle lumière disponible n’est pas ajoutée automatiquement à une configuration existante.
- Un renommage de pièce conserve son identité et ne recrée pas son appareil.

### Appareil et entités de chaque pièce configurée

| Entité | Fonction attendue |
| --- | --- |
| Lumière de la pièce | Allumer selon l’ambiance applicable ; éteindre toutes les lumières sélectionnées. |
| Interrupteur d’éclairage automatique | Autoriser ou suspendre tous les automatismes Halo de la pièce. |
| Interrupteur de lumière naturelle | Activer ou désactiver l’application des profils naturels, sous réserve du mode automatique et des pauses. |
| Bouton de reprise | Réactiver l’automatisation, annuler la pause manuelle et réévaluer la pièce. |
| Entités scène Halo | Permettre le lancement explicite des scènes depuis Home Assistant, notamment d’autres dashboards ou automatisations. |

La lumière de commande reflète les états réels : allumée si au moins une lampe est allumée, éteinte si aucune lampe disponible n’est allumée, indisponible si aucune lampe n’est disponible.

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

### Luminosité et hystérésis

Le capteur de luminosité est facultatif. Lorsqu’il est configuré, l’utilisateur renseigne un seuil fixe et une hystérésis. Le dashboard affiche les seuils effectifs bas et haut ; entre ces seuils, la décision précédente est conservée. Dans l’implémentation, le seuil bas est le seuil renseigné et le seuil haut est ce seuil augmenté de l’hystérésis : la pièce est sombre sous le seuil bas et suffisamment lumineuse à partir du seuil haut.

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

Les valeurs sont interpolées linéairement entre les bornes et restent aux valeurs limites au-delà. Les hauteurs solaires conservent leur précision décimale. Les paramètres incohérents empêchant le calcul doivent être signalés lors de la configuration.

La case **« Lier le matin et le soir »** est cochée par défaut. Elle partage les courbes entre soleil montant et descendant. Décochée, elle permet de régler les deux périodes distinctement. L’éditeur présente un aperçu graphique des courbes.

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

Les scènes sont créées et enregistrées dans Halo. Elles décrivent l’état souhaité des lumières sélectionnées dans leur pièce, avec des contrôles adaptés aux capacités de chaque lampe : marche/arrêt, variation, température du blanc ou couleur.

L’éditeur de conditions propose les états d’entités, seuils numériques, horaires et conditions solaires, combinables avec **ET**, **OU** et **NON**, sans YAML obligatoire.

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
| Transitions globales | Champs vides : aucun paramètre de transition demandé. |
| Transitions par pièce | Héritage des valeurs globales. |
| Courbes matin/soir d’un profil | Liées. |
| Extinction sur forte luminosité | Désactivée. |
| Extinction automatique pendant la pause manuelle | Autorisée ; configurable par pièce. |
| Délai d’absence | 120 secondes, modifiable. |
| Durée de pause manuelle | 15 minutes, modifiable. |
| Confirmation de forte luminosité avant extinction | 30 secondes, modifiable. |
| Seuil lumineux | À renseigner lorsqu’un capteur est configuré. |
| Hystérésis | Zéro, modifiable. |
| Langue de référence et de repli | Anglais. |
| Autre langue fournie | Français, pour `fr` et ses variantes. |

## 14. Scénarios d’acceptation

**Ces scénarios restent la référence d’acceptation complète.** Les tests automatisés couvrent notamment le moteur, les entités, la persistance, les droits, la concurrence et les langues. Leur réussite locale ne vaut pas validation matérielle ou validation de tous les parcours dans une instance Home Assistant ; ces dernières restent à réaliser.

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

Pour chaque scénario réalisé, consigner son résultat, la version examinée et le périmètre : test automatisé, essai d’interface ou essai sur des lumières réelles. Une fonctionnalité implémentée n’est pas automatiquement validée dans Home Assistant.

## 15. Suivi, décisions et publication

Chaque évolution met à jour dans la même tâche la spécification, le statut d’implémentation et les preuves de vérification. Les idées nouvelles restent explicitement proposées jusqu’à leur adoption. Les règles d’interface sont reportées dans `DESIGN.md` et les capacités livrées dans le README.

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

Le développement et les essais précèdent toute publication. La release et la demande d’inclusion HACS suivent ensuite la [procédure documentée](docs/HACS.md). Aucun référencement n’est déclenché par la rédaction de ce cahier des charges.
