# Architecture de la première version de développement

Dernière mise à jour : **10 octobre 2026**.

Les comportements produit restent définis dans [PROJET.md](../PROJET.md). Cette page décrit les contrats du code, sans constituer une validation sur les équipements du logement.

## Cycle de vie et stockage

`async_setup_entry` charge un `HaloManager` dans `ConfigEntry.runtime_data`, démarre les moteurs des pièces enregistrées, inscrit le panneau et charge les plateformes `light`, `switch`, `button`, `scene` et `sensor`. Le déchargement libère les abonnements, les temporisations et le panneau.

La configuration et les échéances de pause sont enregistrées avec `homeassistant.helpers.storage.Store`, version 1, sous la clé `halo.<entry_id>`. Les écritures sont atomiques ; un état inchangé ne provoque pas une nouvelle écriture. La suppression de l’intégration supprime son stockage. Une erreur de lecture ou de validation ne doit pas remplacer la sauvegarde par une configuration vide.

Le document enregistré contient `config`, `revision` et `runtime`. La révision évite qu’une sauvegarde provenant d’un ancien écran écrase une modification plus récente. Les noms de pièces proviennent du registre des zones Home Assistant ; leurs identifiants assurent la stabilité des appareils.

Les changements de mode et la reprise utilisent un commit durable sous le verrou de la pièce, avant publication de la nouvelle configuration/révision ou commande aux lampes. La reprise sauvegarde dans cette transaction l’activation et la suppression de `pause_until`, `manual_scene_id` et `nightlight_blocked`. Un échec d’écriture conserve les valeurs précédentes. Les événements du détecteur peuvent encore enregistrer `absent_since` pendant l’attente du stockage : la publication retire seulement les clés de pause, sans réinjecter un ancien instantané de runtime qui effacerait cet événement. La persistance suivante conserve les données les plus récentes.

Une demande de mode ou de reprise invalide les commandes anciennes avant d’attendre le verrou. Si son commit échoue après avoir interrompu une séquence locale automatique, le moteur réévalue l’ancienne politique uniquement lorsque la génération ayant interrompu la séquence est encore celle de cette demande. Une intention manuelle plus récente interdit cette récupération. Celle-ci ne termine pas la pause existante et ne masque jamais l’exception de stockage initiale ; aucune relance n’est ajoutée en l’absence de séquence locale interrompue.

La suppression d’une pièce filtre également son runtime dans la même écriture. Si l’arrêt de son moteur ou le commit échoue, ses abonnements sont rétablis afin que la pièce encore configurée continue de fonctionner. Deux sauvegardes concurrentes de la même révision ne peuvent pas être acceptées toutes les deux. La suppression du seul appareil Halo utilise l’API `async_remove_device` de la version Home Assistant prise en charge.

### Capteur d’état de la pièce

**Implémenté ; tests locaux du moteur et des plateformes Home Assistant avec lampes simulées.** La plateforme `sensor` ajoute un capteur `Status` par pièce au même appareil que les autres entités Halo, avec une identité liée à l’identifiant stable de zone. Il suit les notifications du moteur sans scrutation ni dépendance au panneau. Le cycle de vie commun assure l’ajout et le retrait dynamiques, le rechargement et la libération de son abonnement.

Le capteur rapporte `off`, `manual`, `natural`, `nightlight` ou le nom d’une scène active. Les quatre valeurs fixes utilisent les traductions natives anglaises/françaises ; les noms personnalisés ne sont pas traduits. L’absence totale de lampe disponible rend l’entité indisponible. Sinon, l’absence de lampe allumée impose `off`, puis une session d’édition impose `manual`. Un nom de scène n’est exposé que pour une scène conditionnelle effectivement appliquée ou une scène explicitement lancée pendant sa pause ; une scène dont les conditions sont simplement vraies ne suffit pas. Le lancement explicite peut rester nommé avec l’automatisation désactivée, jusqu’à une nouvelle intervention manuelle ou à la fin de son application.

L’extension veilleuse ajoute `nightlight` lorsque cette ambiance est effectivement appliquée à au moins une lampe allumée, y compris pendant une pause autorisant ce fonctionnement. Les états indisponible, éteint et édition restent prioritaires. Hors scène ou veilleuse, `natural` exige une application naturelle active et au moins une lampe allumée dans une association concernée. Les autres cas allumés utilisent `manual`, notamment la pause sans scène, le mode automatique désactivé et l’ambiance de base seule. Cette synthèse ne change pas le contrat de statut détaillé envoyé au panneau.

Les attributs `mode`, `scene_id` et `scene_name` permettent de consommer cet état sans dépendre du nom affiché : `mode` vaut `off`, `manual`, `natural`, `nightlight` ou `scene` ; les deux attributs de scène valent `null` hors scène. Un nom exactement égal à `off`, `manual`, `natural`, `nightlight`, `unknown` ou `unavailable` est préfixé par `scene: ` dans la valeur du capteur pour éviter les traductions des états fixes et les sentinelles Home Assistant. `scene_name` conserve le nom exact dans tous les cas.

Le capteur utilise le contrat officiel de [l’entité Sensor](https://developers.home-assistant.io/docs/core/entity/sensor/) et les [traductions d’états d’entités](https://developers.home-assistant.io/docs/internationalization/core/#state-of-entities). L’extension veilleuse a fait l’objet d’un parcours dans Home Assistant 2026.10.0 isolé avec des lampes simulées ; les essais domestiques restent distincts.

## Configuration

La configuration regroupe `sun_entity_id`, `presence_return_window`, `transitions`, `profiles` et `rooms`. Les profils sont indexés par identifiant stable. Les pièces sont indexées par identifiant de zone Home Assistant. Les scènes sont une liste ordonnée dans chaque pièce.

**Extension des scènes implémentée le 10 octobre 2026 :** le modèle Python/TypeScript distingue `type: "halo"` et `type: "home_assistant"`. Les anciennes scènes sans type sont interprétées comme `halo`. Les deux types conservent identifiant stable, nom, conditions et `can_turn_on` ; les scènes Halo utilisent leurs états `lights`, les scènes liées référencent une entité `scene.*` dans `scene_entity_id`. Cette normalisation reste compatible avec le stockage version 1 et les révisions existantes.

**Extension veilleuse implémentée le 10 octobre 2026 :** chaque pièce porte `nightlight: { enabled, lights }`, avec défaut `{ "enabled": false, "lights": {} }` lorsqu’il manque, y compris dans un document existant. `lights` reprend les états reproductibles indexés par entité des scènes Halo. Aucun renommage des champs existants ni changement du stockage version 1 n’est nécessaire. Une activation exige une source de présence et au moins une lampe `on`, avec luminosité non nulle lorsqu’elle est renseignée. Les entités doivent appartenir à la pièce ; retirer une lampe retire son réglage de veilleuse. Les conflits connus où un groupe destiné à l’extinction contient une veilleuse sont refusés ; les groupes opaques restent explicitement signalés par le panneau.

**Autorisation sans capteur — implémentée et vérifiée localement le 10 octobre 2026 :** chaque pièce reçoit `lighting_fallback` avec les champs et défauts suivants, y compris lorsqu’ils manquent dans une configuration existante :

```json
{
  "mode": "always",
  "start": "18:00",
  "end": "08:00",
  "linked": true,
  "morning_below": 0,
  "evening_below": 0,
  "turn_off": false
}
```

`mode` accepte `always`, `time` et `sun`. Les heures sont strictement au format `HH:MM`, valides sur 24 heures et distinctes. `linked` et `turn_off` sont des booléens ; les deux seuils sont des nombres finis de −90 à 90 degrés, booléens exclus. Les champs inconnus ou mal typés sont refusés. Les valeurs des modes inactifs sont conservées et validées ; la liaison matin/soir n’efface pas le seuil du soir. La normalisation ne modifie pas l’objet fourni ni les autres pièces. Le stockage version 1, les révisions et les commandes de configuration restent utilisés sans nouvelle API d’écriture.

Le champ global `presence_return_window` exprime en secondes la durée commune de protection contre les pertes de présence : nombre fini de 0 à 604 800, avec défaut de 30 pour une nouvelle configuration ou un ancien document qui ne contient pas le champ. Il fixe la fenêtre de rallumage rapide après extinction et le minimum supplémentaire d’absence continue avant qu’un retour termine la pause. Zéro désactive le rallumage rapide et ce minimum supplémentaire, sans supprimer le délai d’absence local ; une valeur explicitement enregistrée est conservée. Le champ utilise les commandes de configuration et le stockage version 1 existants, avec validation serveur, droits administrateur et contrôle de révision ; aucune nouvelle commande API n’est nécessaire. L’interface exige une valeur renseignée.

Chaque courbe naturelle contient `low_elevation`, `high_elevation`, `low`, `high` et `interpolation`. Les modes proposés sont `linear` et `ease_in_out`. L’ancien identifiant `ease_in` est accepté et normalisé vers `ease_in_out`, y compris pour les courbes du soir masquées, pour appliquer la correction demandée aux profils existants. Pour les courbes actives, l’absence du champ est normalisée en `linear`, sans changement du stockage version 1 ; une valeur inconnue est rejetée. La normalisation seule n’écrit pas, mais une persistance ultérieure de configuration ou de runtime enregistre la valeur canonique. Les autres paramètres du soir ne sont utilisés et validés que lorsque les périodes sont dissociées. Le choix se fait par courbe de luminosité/température et par branche matin/soir, avec le comportement existant de liaison des branches.

Le moteur Python et l’aperçu TypeScript utilisent le même calcul : `t = clamp((elevation - low_elevation) / (high_elevation - low_elevation), 0, 1)`, puis `low + (high - low) × t` en linéaire ou `low + (high - low) × t² × (3 − 2t)` pour la courbe en S (smoothstep). La pente s’annule aux deux bornes. L’ancien identifiant `ease_in` est aussi interprété ainsi par le lecteur et l’aperçu. Les corrections relatives et limites des lampes s’appliquent ensuite. Le temps écoulé n’intervient pas dans cette interpolation : les transitions des commandes restent indépendantes.

Les réglages sont validés côté serveur avant enregistrement : appartenance unique des lampes, exclusion des lumières Halo, références aux profils, bornes solaires, valeurs numériques finies, capacités de variation et portée des états de scène. Les données indisponibles restent distinctes des valeurs numériques valides.

Les nombres hors limites, y compris les entiers JSON trop grands pour une conversion flottante, et les identifiants de profil de type incorrect sont rejetés comme erreurs de validation. Le parcours des compositions de groupes utilise une pile itérative, un ensemble de nœuds visités et une pile active : les branches partagées ne sont développées qu’une fois, une profondeur élevée n’épuise pas la pile Python et les cycles restent signalés comme incomplets.

Les cinq clés de transition sont `turn_on`, `lux_on`, `natural`, `scene` et `turn_off`. Globalement, une valeur est un nombre de secondes ou `null`. Par pièce, `"inherit"` demande l’héritage, `null` omet le paramètre et un nombre définit la durée locale, y compris zéro.

Les nouvelles configurations utilisent respectivement 0, 10, 60, 10 et 2 secondes. Une pièce créée utilise un délai d’absence de 0 seconde et une pause manuelle de 7 200 secondes (120 minutes dans le panneau). La normalisation préserve les valeurs existantes, y compris `null` et zéro ; elle ne migre pas les réglages enregistrés vers les nouveaux défauts.

L’hystérésis utilise un seuil bas égal au seuil configuré et un seuil haut égal à ce seuil plus l’hystérésis. L’allumage est autorisé sous le seuil bas ; la décision devient « luminosité suffisante » à partir du seuil haut. Entre les deux, la décision précédente est conservée.

Les conditions sont des arbres de types `state`, `numeric`, `time`, `sun`, `and`, `or` et `not`. Une condition absente signifie une scène disponible uniquement pour un lancement explicite. Aucun code, modèle de texte exécutable ou action Home Assistant arbitraire n’est accepté dans cet éditeur.

## Moteur d’une pièce

Chaque moteur écoute ses lampes, ses capteurs, le soleil et les entités de ses conditions. Les échéances utilisent des temporisations dédiées ; un passage toutes les 30 secondes couvre notamment les conditions horaires. La fermeture du panneau n’interrompt pas le moteur.

Le délai planifié est calculé depuis l’heure réelle en fin d’évaluation, après les éventuels appels lents. Une échéance dépassée pendant ces appels déclenche une réévaluation immédiate au lieu de recevoir un délai supplémentaire. Les erreurs de commandes de lampes sont conservées par entité et contribuent à `status.error` : la réussite d’une autre lampe ne les efface pas. Une commande réussie sur l’entité concernée, son retrait de la pièce ou une application native réussie qui la couvre peut les libérer.

Une scène locale déjà appliquée n’est pas rappelée uniquement parce que ses propres réglages laissent la pièce éteinte. Une modification de sélection, une reprise ou un nouveau cycle admissible de présence peut en revanche l’appliquer à nouveau. Les états réels restent prioritaires pour le capteur d’état et pour la décision d’allumage.

Les commandes portent un contexte Home Assistant propre à Halo, relié au contexte utilisateur lorsque disponible. Le moteur suit aussi les valeurs attendues pendant une transition pour les équipements qui ne restituent pas ce contexte. Ce dernier comportement exige encore des essais sur les intégrations de lampes réelles.

### Autorisation d’éclairage sans capteur

**Implémenté et vérifié localement, avec lampes simulées.** La résolution choisit d’abord le capteur lumineux lorsque `lux_entity_id` est configuré. Une mesure inaccessible, non numérique, `unknown` ou `unavailable` reste indisponible ; elle ne sélectionne jamais `lighting_fallback`. En l’absence de capteur, `always` autorise sans mesure, `time` compare l’heure locale Home Assistant à la plage quotidienne `[start, end[`, y compris à travers minuit, et `sun` compare strictement `elevation < seuil` avec la source solaire globale. Lorsque `linked` est vrai, le seuil du matin est partagé ; sinon `rising` sélectionne le matin ou le soir. Les attributs solaires requis absents ou invalides suspendent la décision correspondante.

Cette autorisation reste séparée de la valeur `lux` et de sa mémoire d’hystérésis. Le statut expose `lighting_source`, `lighting_allowed` et `lighting_off_deadline` (date ISO ou `null` pour l’échéance), sans fabriquer une mesure lumineuse. Les changements de présence, de soleil et les bornes horaires réévaluent la pièce ; les bornes horaires disposent d’une échéance dédiée, sans dépendre du passage périodique de 30 secondes. Le calcul emploie le fuseau de Home Assistant plutôt que celui du navigateur ou de l’hôte de test.

Une ouverture pendant une présence ou une absence déjà établie utilise `lux_on`, selon qu’elle déclenche l’ambiance normale ou la veilleuse. Un allumage sur présence utilise `turn_on`, y compris pour reprendre l’ambiance normale complète après la veilleuse. Une fermeture utilise `turn_off` : immédiatement à la fin horaire, ou après `lux_off_delay` de fermeture solaire continue. L’option `lighting_fallback.turn_off` limite l’extinction de l’éclairage normal ; elle ne limite pas celle des veilleuses, toujours soumises à la fermeture. Le mode `always` n’a pas de fermeture.

Les scènes conditionnelles autorisées à allumer conservent leur priorité ; les pauses, l’édition, la désactivation et la priorité des intentions manuelles restent protégées. Les réévaluations ne doivent pas répéter les commandes déjà appliquées. Après reconfiguration ou redémarrage, les décisions et échéances sont recalculées depuis les paramètres et les données disponibles. Les tests et limites propres à ce contrat sont suivis dans [QA-LIGHTING-FALLBACK-2026-10-10.md](QA-LIGHTING-FALLBACK-2026-10-10.md), indépendamment de la recette antérieure.

Sans capteur lumineux, un retour rapide exige une autorisation alternative valide et ouverte lors de l’événement de présence puis au moment de l’application ; il ne contourne ni une fermeture ni une indisponibilité survenue entre les deux. Le réglage `lux_off` conservé après retrait du capteur n’intervient plus dans cette protection : les réglages lumineux inactifs restent mémorisés mais n’influencent pas les décisions sans capteur. La protection historique vis-à-vis d’une mesure lumineuse périmée reste inchangée lorsqu’un capteur est configuré.

### Fenêtre de rallumage après absence

**Implémenté et testé localement ; validation matérielle et déploiement domestique non réalisés pour cet ajout.** Avec un capteur configuré et `lux_off` faux, ou sans capteur sous réserve de l’autorisation alternative, le moteur mémorise en mémoire le début de l’extinction pour absence s’il reste une lampe allumée. Les réévaluations répétées ne repoussent pas cet instant. La fenêtre n’est ni persistée dans `runtime`, ni restaurée après redémarrage.

Un événement de présence doit passer d’un état connu absent à un état présent configuré, strictement avant l’expiration. Un changement d’attributs ou un rétablissement depuis `unknown`/`unavailable` ne suffit pas. La reprise contourne le contrôle lumineux pour cet allumage seulement, sans modifier la mesure ni l’hystérésis. Elle réapplique l’ambiance applicable avec `turn_on`, même si une scène est sélectionnée ou si un fondu d’extinction laisse les lampes temporairement allumées. Les intentions d’extinction encore en attente deviennent caduques ; un événement lumineux ultérieur ne déclenche pas un nouvel allumage avec `lux_on`.

La fenêtre est consommée lors de la reprise. Extinction manuelle, extinction par une scène, extinction sur luminosité et passage en veilleuse ne l’ouvrent pas. Le retour depuis une veilleuse n’utilise pas cette protection pour contourner le seuil lumineux. Intervention manuelle, session d’édition, désactivation et reconfiguration l’annulent. Les protections d’automatisation, d’édition et de pause restent prioritaires ; le retour ne termine la pause que selon la durée minimale d’absence continue décrite ci-dessous. Une nouvelle commande manuelle doit aussi pouvoir invalider le rallumage en attente.

### Retour de présence pendant une pause manuelle

**Implémenté et testé localement ; validation matérielle et déploiement domestique non réalisés pour cet ajout.** La fin de pause au retour nécessite une absence continue d’au moins `max(absence_delay, presence_return_window)` secondes. Ce contrôle s’applique à toutes les pièces, quel que soit `lux_off`. L’expiration de ce délai pendant l’absence ne termine pas la pause ; seul le retour présent le fait, en dehors de l’expiration propre de pause ou d’une reprise explicite, qui restent inchangées.

Les états personnalisés du détecteur déterminent présence et absence. `unknown` ou `unavailable` rompt la continuité et ne prolonge pas artificiellement une absence connue. Zéro comme valeur globale retire seulement le minimum supplémentaire : `absence_delay` reste exigé pour le retour. L’extinction automatique utilise toujours son délai local et la fenêtre de rallumage reste comptée depuis l’envoi de cette extinction. Si un retour intervient alors que la pause est encore protégée, cette pause conserve sa priorité ; aucun instantané d’ambiance manuelle n’est ajouté ou réappliqué par ce mécanisme.

### Veilleuse pendant l’absence

**Implémenté ; tests automatisés et parcours Home Assistant isolé avec des lampes simulées.** Le moteur distingue l’application d’une veilleuse (`nightlight`) de celle d’une ambiance normale. Après absence confirmée, sans scène prioritaire autorisée à allumer, il applique les états fixes configurés et éteint les autres lampes. Si la luminosité baisse pendant une absence déjà confirmée, il allume les seules veilleuses. Sans capteur et en mode `always`, l’absence suffit ; l’extension `lighting_fallback` décrite ci-dessus soumet cette autorisation au mode horaire ou solaire choisi. Une source lumineuse configurée mais indisponible suspend les nouvelles décisions qui dépendent de sa mesure.

Le seuil, l’hystérésis et le délai de confirmation existants sont réutilisés. L’extinction lumineuse de la veilleuse n’est pas soumise à `lux_off` : elle s’applique après confirmation du seuil haut, même lorsque ce réglage est faux. La présence inconnue n’est jamais une absence et la luminosité inconnue n’est jamais zéro. Les ajustements naturels ne commandent pas les veilleuses pendant ce mode.

Au retour présent, l’ambiance normale complète est réappliquée si le seuil le permet, même si une veilleuse se déclare déjà allumée. Sinon, le moteur conserve l’attente lumineuse et éteint les veilleuses après confirmation ; une baisse ultérieure peut appliquer l’ambiance normale. Il utilise `turn_off` pour le passage de l’ambiance normale à la veilleuse et pour son extinction, `lux_on` pour son allumage après baisse lumineuse, `turn_on` pour la reprise normale immédiate sur présence, ou `lux_on` si cette reprise attend la luminosité. Les générations de commandes rendent caduques les intentions remplacées par un retour ou une nouvelle commande manuelle.

Édition et désactivation suspendent la veilleuse. Une pause autorisant les extinctions permet de remplacer celle d’absence par la veilleuse sans terminer la pause ; une extinction manuelle explicite de toute la pièce bloque son rallumage pour la durée de cette pause. Le blocage est persisté dans `runtime` avec l’échéance de pause puis supprimé à sa fin ou à la reprise explicite. Le mode veilleuse lui-même est recalculé depuis les données disponibles au redémarrage ; les réévaluations n’envoient pas les mêmes réglages en boucle.

### Session d’édition

Une session d’édition possède un jeton aléatoire, une seule connexion propriétaire et un instantané initial. Le panneau renouvelle sa session ; l’expiration intervient après 120 secondes sans renouvellement. Enregistrement et restauration sont traités côté serveur. Une autre connexion ne peut pas utiliser le jeton pour commander les lampes.

### Application d’une scène Home Assistant liée

**Implémenté et vérifié localement.** Un chemin commun d’application choisit entre les commandes de lampes d’une scène Halo et l’action native `scene.turn_on` sur `scene_entity_id`. Il sert à l’arbitrage automatique, à l’allumage de la pièce et au lancement explicite d’une scène. Le lien ne lit ni `scenes.yaml` ni les objets internes du fournisseur et n’utilise aucune activation pour découvrir sa configuration. Home Assistant exécute la source entière, effets compris. [Action native et scènes d’intégrations](https://www.home-assistant.io/integrations/scene/).

La catégorie de transition provient du déclencheur existant (`turn_on`, `lux_on` ou `scene`). Une durée explicite est plafonnée à 6 553 secondes avant l’appel ; `null` omet le paramètre, `0` reste explicite. La prise en charge matérielle dépend de la scène et du fournisseur. La scène n’est marquée appliquée qu’après réussite de l’appel. Les réévaluations périodiques et changements de timestamp de la source ne doivent pas provoquer de réactivation.

Une source absente ou `unavailable` est inéligible, tandis que `unknown` est valide pour une scène jamais activée. L’arbitrage automatique signale une source inaccessible ou un échec d’activation et poursuit avec la suivante, sinon l’ambiance normale, sans boucle de relance immédiate. Un lancement explicite échoué renvoie une erreur. À la sortie de scène, le moteur reprend uniquement les lumières de sa pièce ; il ne restaure pas les équipements extérieurs affectés par la source.

Avant un lancement explicite, les droits de contrôle sur la source sont vérifiés en plus des droits existants de la pièce. L’appel natif transmet le contexte utilisateur. Les entités scène Halo et les sources connues pour commander des entités Halo sont refusées. Une garde contre les appels récursifs intervient avant les verrous des moteurs pour éviter un interblocage. Une désactivation autorisée invalide les intentions et suspend temporairement les réévaluations en file avant d’attendre le verrou de configuration ; cette suspension est libérée même si la demande est annulée. Cela ne peut annuler rétroactivement une commande déjà reçue par un fournisseur.

`status.scene_errors` associe les identifiants Halo des scènes aux codes `external_scene_unavailable`, `external_scene_recursive` ou `external_scene_failed`. Les erreurs sont traduites dans la liste. Un échec automatique reste écarté jusqu’à un changement de conditions, au rétablissement de la source ou à une reprise/reconfiguration ; son timestamp seul ne le réarme pas.

Le contexte de la commande est reconnu prioritairement. Une tolérance distincte couvre ensuite les retours sans origine identifiable pendant la transition réellement transmise + 5 secondes depuis le lancement, ou 5 secondes si aucune transition n’est demandée. Elle porte sur les lampes concernées dans la pièce ; si la composition est inconnue, elle couvre toutes les lampes de cette pièce. Elle ne masque pas les commandes manuelles identifiées et ne s’étend pas aux autres pièces. Une intervention physique sans contexte pendant ce délai peut ne pas déclencher de pause. Échec, intervention manuelle, édition, désactivation et reconfiguration annulent cette tolérance temporaire.

## Panneau et WebSocket

Les sources sont dans `frontend/src/`. Le bundle Lit autonome est distribué dans `custom_components/halo/frontend/halo-panel.js`, servi localement sous `/halo_frontend/halo-panel.js`. Aucun CDN ni carte supplémentaire n’est nécessaire.

Une sauvegarde transmet une copie du brouillon et mémorise son compteur de modification. Son acquittement conserve les saisies faites entre-temps et fournit la révision du prochain enregistrement ; une révision distante plus récente déclenche toujours le contrôle de conflit. Les réponses asynchrones d’une connexion ou de droits précédents ne remplacent pas la configuration courante. Changer de connexion invalide l’éditeur, son renouvellement et ses réponses ; perdre les droits administrateur retire les formulaires privilégiés. La révision d’une session d’édition est figée avant l’acquisition du verrou : si elle change pendant l’attente, le verrou est annulé sans aperçu. La sécurité des écritures reste contrôlée côté serveur.

| Commande | Accès | Rôle |
| --- | --- | --- |
| `halo/get` | Utilisateur authentifié | Configuration, zones, lumières, états et révision. |
| `halo/subscribe` | Utilisateur authentifié | Instantané initial puis mises à jour ; abonnement conservé lors d’un rechargement de l’intégration. |
| `halo/command` | Utilisateur autorisé à piloter les lampes | Allumer, éteindre, changer un mode, reprendre ou lancer une scène. |
| `halo/save` | Administrateur | Enregistrer une configuration avec sa révision. |
| `halo/scene/import` | Administrateur | Filtrer et normaliser une configuration de scène Home Assistant en brouillon, sans stockage ni commande matérielle. |
| `halo/scene/inspect` | Administrateur | Inspecter les métadonnées d’une source et leur portée dans la pièce, sans stockage ni activation. |
| `halo/edit/begin` | Administrateur | Verrouiller l’édition d’une pièce et obtenir son jeton. |
| `halo/edit/preview` | Administrateur propriétaire | Appliquer l’aperçu aux lampes de la pièce. |
| `halo/edit/touch` | Administrateur propriétaire | Renouveler la session. |
| `halo/edit/end` | Administrateur propriétaire | Enregistrer la scène ou la veilleuse ciblée, ou annuler puis libérer l’édition. |

Les permissions Home Assistant filtrent les états lisibles et contrôlent les commandes de lampes. Les erreurs possèdent un code traduit par le panneau, notamment `invalid_config`, `conflict`, `edit_locked` et `invalid_edit`.

### Navigation, brouillon et thème

La refonte compacte ne change aucun contrat WebSocket, REST ni stockage. L’état de navigation du panneau sélectionne les pièces, les profils ou les réglages globaux. Dans une pièce, une sous-vue choisit le pilotage, les lumières, l’automatisation, les ambiances ou les réglages. Les profils ont une sélection distincte et un seul éditeur monté à la fois. La liste de pièces et le détail partagent l’écran sur ordinateur ; la feuille de style affiche successivement ces deux zones sur mobile.

Le brouillon et sa révision restent indépendants des sous-vues. Les champs valides alimentent le modèle dès la saisie. Une entrée numérique invalide est conservée dans le contrôle, sans valeur de remplacement artificielle ; la validation empêche de quitter la sous-vue et focalise le champ. Les sections `details` contenant une erreur sont ouvertes avant sa présentation, y compris pour une condition d’édition. Les bornes solaires sont aussi contrôlées côté panneau. L’abandon utilise une nouvelle clé Lit pour remonter le contenu et effacer les saisies invalides absentes du modèle. Le serveur demeure responsable de la validation complète et des conflits de révision.

Les onglets utilisent les rôles `tablist`, `tab`, `tabpanel`, un seul arrêt de tabulation et les touches fléchées, Début et Fin. La navigation est bloquée pendant une session d’édition réelle. Une annulation d’import redonne le focus au bouton d’import ; sa confirmation cible la nouvelle ligne de scène, car les actions de cette scène ne deviennent disponibles qu’après sauvegarde. La fin d’une édition revient à son bouton de réglage ou à la création d’une scène. Une édition de veilleuse revient à Ambiances et à son bouton Configurer ; elle n’ajoute pas d’onglet ni de scène.

Les styles du panneau et du sélecteur Halo lisent les variables Home Assistant pour les couleurs, états, police, tailles, espacements, bordures, rayons, en-tête et champs. Les valeurs de repli restent locales aux propriétés manquantes ; aucune palette claire/sombre séparée n’est définie par Halo. Le panneau règle `color-scheme` selon `hass.themes.darkMode` lorsqu’il est présent et retire cette surcharge sinon. Les icônes passent par `ha-icon` ; la réduction des mouvements supprime les animations et transitions CSS. Ces choix ne supposent pas le chargement de composants privés de formulaire.

### Inspection et configuration d’une scène liée

`halo/scene/inspect` reçoit `room_id` et `entity_id` (entité scène source). Il retourne `entity_id`, `name`, `available`, `complete`, `lights`, `outside_lights`, `missing_lights`, `other_entities` et `blocked`. La réponse distingue les lampes extérieures, les lampes de la pièce non concernées et la complétude de la composition connue. Seules les métadonnées exposées par Home Assistant sont utilisées. Les groupes sont développés pour la comparaison lorsque leurs membres sont connus ; un groupe sans membres exposés ou une source opaque empêche de présenter cette comparaison comme exhaustive. Aucun identifiant inaccessible ne doit être divulgué.

Le panneau utilise le sélecteur Halo existant et exclut les entités de scène Halo. Le menu « Ajouter une scène » distingue création, lien et import ; le formulaire de lien édite uniquement source, nom et règles. La confirmation alimente le brouillon, puis `halo/save` applique les droits, la validation et les contrôles de révision habituels. L’ajout d’une scène manuelle sans condition et les changements de nom seuls rafraîchissent les dépendances sans rappel matériel ; les modifications de source ou de règles enregistrées réévaluent normalement les automatismes. `halo/command` et les entités scène des appareils Halo utilisent le même chemin de lancement pour les deux types. La configuration d’un lien n’ouvre aucune session `halo/edit/*` et n’applique aucun aperçu.

### Import de scènes Home Assistant

Le panneau lit la configuration native par `hass.callApi("GET", "config/scene/config/{id}")`, avec l’identifiant de configuration `attributes.id` encodé comme segment d’URL. Ce n’est pas l’identifiant d’entité `scene.*`. Le frontend officiel utilise [ce même endpoint](https://github.com/home-assistant/frontend/blob/20260930.2/src/data/scene.ts#L147) ; la [vue du cœur](https://github.com/home-assistant/core/blob/2026.10.0/homeassistant/components/config/view.py) contrôle les droits administrateur et lit `scenes.yaml`. Cette dépendance est isolée et vérifiée sur la version prise en charge, sans prétendre à un contrat REST public stable. Aucun accès direct aux fichiers de configuration Home Assistant, objet privé d’intégration ou activation globale de scène n’est nécessaire.

La commande `halo/scene/import` reçoit `room_id` et `config` (configuration native avec `name` et `entities`), et retourne `scene` et `ignored_entities`. Le serveur intersecte les identifiants avec les lampes de la pièce avant de normaliser les valeurs. Une absence de correspondance produit `no_matching_lights` ; un réglage retenu invalide produit `invalid_config`. Les entités extérieures, les domaines autres que `light` et les attributs descriptifs ne deviennent jamais des paramètres de commande. Les groupes ne sont pas développés.

La normalisation suit la [reproduction des états `light` de Home Assistant](https://github.com/home-assistant/core/blob/2026.10.0/homeassistant/components/light/reproduce_state.py) : état simple ou objet, booléens YAML convertis en `on`/`off`, luminosité native et effet, représentation désignée par `color_mode`, ou priorité native en son absence. Le blanc simple utilise la luminosité. Une extinction conserve uniquement `state: off`, sans les anciens attributs de couleur. La validation Halo contrôle ensuite les valeurs reproductibles ; elle n’utilise jamais l’état courant d’une lampe pour remplacer un réglage importé.

Le résultat possède un nouvel identifiant, sans condition et sans autorisation d’allumage automatique. Il est ajouté au brouillon, puis sauvegardé avec `halo/save` et sa révision. La lecture, la normalisation et l’ajout ne commandent aucune lampe. La sauvegarde d’un simple ajout de scènes manuelles n’impose pas de réapplication de l’ambiance. Une copie ne conserve aucune liaison fonctionnelle avec la scène source.

Les scènes sans `id`, absentes de `scenes.yaml` ou fournies par une intégration tierce sans configuration lisible ne sont pas récupérées par activation/capture. Le panneau explique leur indisponibilité et conserve son brouillon en cas d’erreur, de réponse tardive ou de conflit de révision. Une scène native porte souvent un attribut `entity_id` ; cela ne la classe pas parmi les groupes de lampes. Ses références d’entités restent filtrées selon les droits de lecture de l’utilisateur.

### Édition et sauvegarde de la veilleuse

Le contrat étend `halo/edit/end` avec `target: "scene" | "nightlight"`, facultatif et égal à `"scene"` par défaut pour les clients existants. Pour enregistrer, la cible `"nightlight"` reçoit `save: true`, `nightlight: { enabled, lights }`, `revision` et, pour la capture réelle, `capture: true` avec `capture_entities` contenant la sélection explicite du panneau. Aucun identifiant, nom ou condition de scène n’est créé. La sélection doit être valide, sans doublon et limitée aux lampes de la pièce. Comme pour les scènes, l’absence de `capture_entities` conserve la capture de toute la pièce pour compatibilité ; le nouveau panneau transmet toujours sa sélection.

La capture, la validation et la persistance atomique interviennent sous les mêmes droits, révision et verrou de session que les scènes. La session n’est libérée qu’après succès. Annulation et expiration restaurent l’instantané initial ; une erreur ne laisse pas une sauvegarde partielle. Les états indisponibles ne remplacent pas un réglage reproductible déjà connu. L’activation et la configuration ordinaire restent enregistrées par le brouillon transversal ; démarrer une édition réelle exige d’avoir enregistré ou abandonné ce brouillon.

### Contrôles natifs des lampes dans les scènes

La liste des lampes appartient à Halo. Un clic émet l’événement documenté `hass-action`, avec `config.entity`, `tap_action.action = "more-info"`, `action = "tap"`, `bubbles` et `composed`. Home Assistant ouvre lui-même sa fenêtre et envoie les commandes avec les droits de l’utilisateur. Le panneau ne charge pas directement `more-info-light`, n’intercepte pas ses commandes et n’injecte pas de contexte interne. Fermer la fenêtre ne clôt pas la session d’édition Halo.

La prévisualisation initiale d’une scène existante se termine avant l’ouverture des contrôles ; aucun ancien aperçu ne doit ensuite écraser les commandes natives. Le panneau renouvelle la session avant chaque ouverture. L’enregistrement utilise `halo/edit/end` avec `capture: true` : le serveur capture les états sous le verrou d’édition, valide la scène puis la persiste avant de libérer la session. L’option absente conserve le contrat précédent de sauvegarde des valeurs fournies.

`capture_entities`, facultatif sur `halo/edit/end`, limite cette capture aux identifiants inclus dans la scène. Il exige `save: true` et `capture: true`, une liste sans doublon et uniquement des membres de la pièce. Son absence conserve la capture de toute la pièce pour les anciens clients. Le panneau transmet sa sélection explicite et n’ajoute pas les autres lampes lors de la réouverture d’une scène partielle. Le stockage reste inchangé : les clés de `scene.lights` représentent les inclusions enregistrées ; aucun champ de migration n’est nécessaire.

Les instantanés conservent l’état, la luminosité native, l’effet et la seule couleur active désignée par `color_mode`. RGBW/RGBWW conservent leurs canaux blancs. Le mode blanc simple se réapplique avec `white`. Les anciens réglages en pourcentage restent acceptés. Les attributs descriptifs, listes d’effets et autres données non reproductibles ne sont pas transmis à `light.turn_on`. Une extinction ne réapplique pas la couleur ou l’effet en rallumant la lampe. Les valeurs indisponibles ne remplacent pas un réglage mémorisé.

Fondements vérifiés dans la documentation et les sources officielles :

- [Action `hass-action`](https://developers.home-assistant.io/blog/2023/07/07/action-event-custom-cards/) et [action `more-info`](https://www.home-assistant.io/dashboards/actions/).
- [Gestion des actions à la racine du frontend 20260930.2](https://github.com/home-assistant/frontend/blob/20260930.2/src/state/action-mixin.ts) : l’événement peut remonter depuis le panneau personnalisé.
- [Éditeur natif de scènes](https://github.com/home-assistant/frontend/blob/20260930.2/src/panels/config/scene/ha-scene-editor.ts) : ouverture de la fenêtre d’entité et capture des états réels lors de la sauvegarde.
- [Contrat des lumières](https://developers.home-assistant.io/docs/core/entity/light/) et [reproduction des états dans Home Assistant 2026.10.0](https://github.com/home-assistant/core/blob/2026.10.0/homeassistant/components/light/reproduce_state.py).
- [Avertissement historique sur les composants internes](https://developers.home-assistant.io/blog/2020/10/02/lazymoreinfo/) et [précision plus récente de juillet 2026](https://developers.home-assistant.io/blog/2026/07/31/frontend-component-updates-2026.8/) : leur réutilisation est possible, mais les API internes peuvent changer. Le parcours de scène utilise l’action publique plutôt qu’un import de composant.
- [Distribution des intégrations HACS](https://www.hacs.xyz/docs/publish/integration/) et [extensions de dashboard HACS](https://www.hacs.xyz/docs/publish/plugin/) : ces catégories distribuent du code ; elles ne fournissent pas une API supplémentaire pour les composants Home Assistant.

Le catalogue anglais est la référence, avec traduction française. Le panneau lit la langue effective de l’interface pour chaque utilisateur ; les variantes françaises utilisent le français, les autres langues l’anglais.

Le catalogue des lumières expose `is_group`, `group_members` et `member_of`. Le registre (plateforme `group`) et l’attribut de membres `entity_id` fournissent les groupes connus. Les listes, tuples, ensembles et ensembles immuables sont acceptés, normalisés en listes détachées ; les ensembles sont triés. Hue expose aussi le marqueur booléen `is_hue_group` ; le registre Hue avec `translation_key=hue_grouped_light` identifie les groupes v2 même indisponibles. Hue v1 peut signaler un groupe sans exposer ses membres. Les appartenances sont directes ; les identifiants non lisibles sont filtrés, y compris dans les attributs renvoyés. Le panneau peut recevoir d’anciens instantanés sans ces métadonnées et indique alors que l’information manque.

Le panneau occupe la hauteur dynamique de la fenêtre (`100dvh`, avec repli `100vh`). Les listes et zones de détail défilent dans l’espace disponible ; l’en-tête et la barre d’enregistrement occupent leur propre espace, sans recouvrir les formulaires. Les transitions sont présentées en lignes de grille alignant le titre, le choix d’héritage local et la durée, puis s’adaptent à la largeur mobile. L’éditeur de scène conserve ses actions accessibles en bas de sa zone de défilement.

Le composant Lit `halo-entity-picker` recherche les entités par nom et identifiant, sans tenir compte de la casse ou des accents. Il ne modifie la valeur qu’au choix explicite d’un résultat ou à son effacement ; une recherche abandonnée reste sans effet sur la configuration. Le panneau appelle sa validation avant sauvegarde et avant de quitter une sous-vue modifiée, y compris dans l’éditeur de conditions lors de son enregistrement. Les seuils de luminosité reprennent l’unité native du capteur sans conversion.

### Sélecteurs d’entités natifs

La demande de remplacer tous les sélecteurs par le composant natif a été étudiée le 9 octobre 2026, sans modification des sélecteurs. Il ne s’agit pas d’une impossibilité technique ni d’une interdiction générale de réutiliser les composants. La limite identifiée est l’absence de mécanisme public garantissant le chargement du sélecteur au premier accès direct à un panneau personnalisé.

Les voies documentées sont les [flux de formulaire natifs](https://developers.home-assistant.io/docs/data_entry_flow_index/) et [`getConfigForm()` pour l’éditeur d’une carte Lovelace](https://developers.home-assistant.io/docs/frontend/custom-ui/custom-card/#using-the-built-in-form-editor). Les [contextes frontend](https://developers.home-assistant.io/docs/frontend/data/#context) fournissent données et méthodes, mais ne chargent pas les éléments. Dans le frontend 20260930.2, ce chargement passe par le dictionnaire interne `LOAD_ELEMENTS` de [`ha-selector`](https://github.com/home-assistant/frontend/blob/20260930.2/src/components/ha-selector/ha-selector.ts) ; les [helpers publics de cartes](https://github.com/home-assistant/frontend/blob/20260930.2/src/panels/lovelace/custom-card-helpers.ts) n’offrent pas de chargeur de sélecteurs, et [`ha-panel-custom`](https://github.com/home-assistant/frontend/blob/20260930.2/src/panels/custom/ha-panel-custom.ts) ne garantit pas leur préchargement.

Conformément à la demande de ne pas introduire de solution fragile, Halo ne force pas le chargement de Lovelace, ne fabrique pas de faux éditeur de carte et n’importe pas de chunk interne compilé. Les sélecteurs actuels restent utilisés. Déplacer la configuration vers les flux natifs ou vers une véritable carte serait un changement de parcours produit, non décidé à ce stade.

Les identifiants des nouveaux profils et scènes sont des UUID v4 générés avec `crypto.getRandomValues`, disponible également sur HTTP local. Ils ne dépendent plus de `crypto.randomUUID`, réservé aux contextes sécurisés. Les jetons de session d’édition restent créés et vérifiés par le serveur. [Disponibilité de l’API Web Crypto](https://developer.mozilla.org/en-US/docs/Web/API/Crypto/getRandomValues).

## Vérification

La [recette transversale du 10 octobre 2026](QA-2026-10-10.md) complète les validations historiques ci-dessous. Elle inventorie les 68 critères d’acceptation en séparant tests automatisés, essais de services dans Home Assistant isolé, parcours navigateur et limites matérielles ; elle ne revendique pas 68 parcours complets sur des équipements physiques. Les échecs disque, commandes lentes, réponses tardives et autres régressions corrigées y sont rattachés à leurs tests.

Les tests Python emploient Home Assistant et son API WebSocket authentifiée avec des lampes simulées. À l’issue de l’ajout veilleuse le 10 octobre 2026, les **437 tests Python**, les **73 tests frontend**, les contrôles Ruff et TypeScript et la construction du panneau réussissent. La couverture comprend notamment navigation, brouillons, validation, droits, focus, capture des réglages et comportements de la veilleuse. Des essais ciblés d’import, d’édition native et de veilleuse ont également été réalisés dans Home Assistant 2026.10.0 isolé. Pour la veilleuse, les parcours sur ordinateur et mobile couvrent la fenêtre native, la sélection et l’annulation ; les états simulés vérifient aussi l’absence, la luminosité, le retour, l’absence de capteur lumineux et la conservation du blocage manuel au rechargement de l’intégration. Les preuves, le build et les limites sont décrits dans [DEVELOPMENT.md](DEVELOPMENT.md). Ces vérifications ne remplacent pas l’installation domestique et les essais matériels prévus dans le cahier des charges.
