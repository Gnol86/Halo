# Architecture de la première version de développement

Les comportements produit restent définis dans [PROJET.md](../PROJET.md). Cette page décrit les contrats du code, sans constituer une validation sur les équipements du logement.

## Cycle de vie et stockage

`async_setup_entry` charge un `HaloManager` dans `ConfigEntry.runtime_data`, démarre les moteurs des pièces enregistrées, inscrit le panneau et charge les plateformes `light`, `switch`, `button` et `scene`. Le déchargement libère les abonnements, les temporisations et le panneau.

La configuration et les échéances de pause sont enregistrées avec `homeassistant.helpers.storage.Store`, version 1, sous la clé `halo.<entry_id>`. Les écritures sont atomiques ; un état inchangé ne provoque pas une nouvelle écriture. La suppression de l’intégration supprime son stockage. Une erreur de lecture ou de validation ne doit pas remplacer la sauvegarde par une configuration vide.

Le document enregistré contient `config`, `revision` et `runtime`. La révision évite qu’une sauvegarde provenant d’un ancien écran écrase une modification plus récente. Les noms de pièces proviennent du registre des zones Home Assistant ; leurs identifiants assurent la stabilité des appareils.

## Configuration

La configuration regroupe `sun_entity_id`, `transitions`, `profiles` et `rooms`. Les profils sont indexés par identifiant stable. Les pièces sont indexées par identifiant de zone Home Assistant. Les scènes sont une liste ordonnée dans chaque pièce.

Chaque courbe naturelle contient `low_elevation`, `high_elevation`, `low`, `high` et `interpolation`. Les modes autorisés sont `linear` et `ease_in`. Pour les courbes actives, l’absence du champ est normalisée en `linear`, pour préserver les profils historiques sans changement du stockage version 1 ; une valeur inconnue est rejetée. Comme les autres paramètres, les courbes du soir ne sont utilisées et validées que lorsque les périodes sont dissociées. Le choix se fait par courbe de luminosité/température et par branche matin/soir, avec le comportement existant de liaison des branches.

Le moteur Python et l’aperçu TypeScript utilisent le même calcul : `t = clamp((elevation - low_elevation) / (high_elevation - low_elevation), 0, 1)`, puis `low + (high - low) × t` en linéaire ou `low + (high - low) × t²` en accélération progressive. Les corrections relatives et limites des lampes s’appliquent ensuite. Le temps écoulé n’intervient pas dans cette interpolation : les transitions des commandes restent indépendantes.

Les réglages sont validés côté serveur avant enregistrement : appartenance unique des lampes, exclusion des lumières Halo, références aux profils, bornes solaires, valeurs numériques finies, capacités de variation et portée des états de scène. Les données indisponibles restent distinctes des valeurs numériques valides.

Les cinq clés de transition sont `turn_on`, `lux_on`, `natural`, `scene` et `turn_off`. Globalement, une valeur est un nombre de secondes ou `null`. Par pièce, `"inherit"` demande l’héritage, `null` omet le paramètre et un nombre définit la durée locale, y compris zéro.

Les nouvelles configurations utilisent respectivement 0, 10, 60, 10 et 2 secondes. Une pièce créée utilise un délai d’absence de 0 seconde et une pause manuelle de 7 200 secondes (120 minutes dans le panneau). La normalisation préserve les valeurs existantes, y compris `null` et zéro ; elle ne migre pas les réglages enregistrés vers les nouveaux défauts.

L’hystérésis utilise un seuil bas égal au seuil configuré et un seuil haut égal à ce seuil plus l’hystérésis. L’allumage est autorisé sous le seuil bas ; la décision devient « luminosité suffisante » à partir du seuil haut. Entre les deux, la décision précédente est conservée.

Les conditions sont des arbres de types `state`, `numeric`, `time`, `sun`, `and`, `or` et `not`. Une condition absente signifie une scène disponible uniquement pour un lancement explicite. Aucun code, modèle de texte exécutable ou action Home Assistant arbitraire n’est accepté dans cet éditeur.

## Moteur d’une pièce

Chaque moteur écoute ses lampes, ses capteurs, le soleil et les entités de ses conditions. Les échéances utilisent des temporisations dédiées ; un passage toutes les 30 secondes couvre notamment les conditions horaires. La fermeture du panneau n’interrompt pas le moteur.

Les commandes portent un contexte Home Assistant propre à Halo, relié au contexte utilisateur lorsque disponible. Le moteur suit aussi les valeurs attendues pendant une transition pour les équipements qui ne restituent pas ce contexte. Ce dernier comportement exige encore des essais sur les intégrations de lampes réelles.

Une session d’édition possède un jeton aléatoire, une seule connexion propriétaire et un instantané initial. Le panneau renouvelle sa session ; l’expiration intervient après 120 secondes sans renouvellement. Enregistrement et restauration sont traités côté serveur. Une autre connexion ne peut pas utiliser le jeton pour commander les lampes.

## Panneau et WebSocket

Les sources sont dans `frontend/src/`. Le bundle Lit autonome est distribué dans `custom_components/halo/frontend/halo-panel.js`, servi localement sous `/halo_frontend/halo-panel.js`. Aucun CDN ni carte supplémentaire n’est nécessaire.

| Commande | Accès | Rôle |
| --- | --- | --- |
| `halo/get` | Utilisateur authentifié | Configuration, zones, lumières, états et révision. |
| `halo/subscribe` | Utilisateur authentifié | Instantané initial puis mises à jour ; abonnement conservé lors d’un rechargement de l’intégration. |
| `halo/command` | Utilisateur autorisé à piloter les lampes | Allumer, éteindre, changer un mode, reprendre ou lancer une scène. |
| `halo/save` | Administrateur | Enregistrer une configuration avec sa révision. |
| `halo/edit/begin` | Administrateur | Verrouiller l’édition d’une pièce et obtenir son jeton. |
| `halo/edit/preview` | Administrateur propriétaire | Appliquer l’aperçu aux lampes de la pièce. |
| `halo/edit/touch` | Administrateur propriétaire | Renouveler la session. |
| `halo/edit/end` | Administrateur propriétaire | Enregistrer la scène ou annuler puis libérer l’édition. |

Les permissions Home Assistant filtrent les états lisibles et contrôlent les commandes de lampes. Les erreurs possèdent un code traduit par le panneau, notamment `invalid_config`, `conflict`, `edit_locked` et `invalid_edit`.

Le catalogue anglais est la référence, avec traduction française. Le panneau lit la langue effective de l’interface pour chaque utilisateur ; les variantes françaises utilisent le français, les autres langues l’anglais.

Le catalogue des lumières expose `is_group`, `group_members` et `member_of`. Le registre (plateforme `group`) et l’attribut de membres `entity_id` fournissent les groupes connus. Les listes, tuples, ensembles et ensembles immuables sont acceptés, normalisés en listes détachées ; les ensembles sont triés. Hue expose aussi le marqueur booléen `is_hue_group` ; le registre Hue avec `translation_key=hue_grouped_light` identifie les groupes v2 même indisponibles. Hue v1 peut signaler un groupe sans exposer ses membres. Les appartenances sont directes ; les identifiants non lisibles sont filtrés, y compris dans les attributs renvoyés. Le panneau peut recevoir d’anciens instantanés sans ces métadonnées et indique alors que l’information manque.

Le panneau occupe la hauteur dynamique de la fenêtre (`100dvh`, avec repli `100vh`). Seule la zone de contenu défile ; l’en-tête et la barre d’enregistrement occupent leur propre espace, sans recouvrir les formulaires. Les champs de transition partagent leurs rangées grâce à CSS subgrid, pour aligner les contrôles indépendamment de la longueur des titres.

Le composant Lit `halo-entity-picker` recherche les entités par nom et identifiant, sans tenir compte de la casse ou des accents. Il ne modifie la valeur qu’au choix explicite d’un résultat ou à son effacement ; une recherche abandonnée reste sans effet sur la configuration. Le panneau appelle sa validation avant sauvegarde, y compris dans l’éditeur de conditions. Les seuils de luminosité reprennent l’unité native du capteur sans conversion.

Les identifiants des nouveaux profils et scènes sont des UUID v4 générés avec `crypto.getRandomValues`, disponible également sur HTTP local. Ils ne dépendent plus de `crypto.randomUUID`, réservé aux contextes sécurisés. Les jetons de session d’édition restent créés et vérifiés par le serveur. [Disponibilité de l’API Web Crypto](https://developer.mozilla.org/en-US/docs/Web/API/Crypto/getRandomValues).

## Vérification

Les tests Python emploient Home Assistant et son API WebSocket authentifiée avec des lampes simulées. Les tests du panneau et son build sont décrits dans [DEVELOPMENT.md](DEVELOPMENT.md). Ces vérifications ne remplacent pas l’installation et les essais matériels prévus dans le cahier des charges.
