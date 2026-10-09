# Architecture de la première version de développement

Les comportements produit restent définis dans [PROJET.md](../PROJET.md). Cette page décrit les contrats du code, sans constituer une validation sur les équipements du logement.

## Cycle de vie et stockage

`async_setup_entry` charge un `HaloManager` dans `ConfigEntry.runtime_data`, démarre les moteurs des pièces enregistrées, inscrit le panneau et charge les plateformes `light`, `switch`, `button`, `scene` et `sensor`. Le déchargement libère les abonnements, les temporisations et le panneau.

La configuration et les échéances de pause sont enregistrées avec `homeassistant.helpers.storage.Store`, version 1, sous la clé `halo.<entry_id>`. Les écritures sont atomiques ; un état inchangé ne provoque pas une nouvelle écriture. La suppression de l’intégration supprime son stockage. Une erreur de lecture ou de validation ne doit pas remplacer la sauvegarde par une configuration vide.

Le document enregistré contient `config`, `revision` et `runtime`. La révision évite qu’une sauvegarde provenant d’un ancien écran écrase une modification plus récente. Les noms de pièces proviennent du registre des zones Home Assistant ; leurs identifiants assurent la stabilité des appareils.

### Capteur d’état de la pièce

**Implémenté ; tests locaux du moteur et des plateformes Home Assistant avec lampes simulées.** La plateforme `sensor` ajoute un capteur `Status` par pièce au même appareil que les autres entités Halo, avec une identité liée à l’identifiant stable de zone. Il suit les notifications du moteur sans scrutation ni dépendance au panneau. Le cycle de vie commun assure l’ajout et le retrait dynamiques, le rechargement et la libération de son abonnement.

Le capteur rapporte `off`, `manual`, `natural` ou le nom d’une scène active. Les trois valeurs fixes utilisent les traductions natives anglaises/françaises ; les noms personnalisés ne sont pas traduits. L’absence totale de lampe disponible rend l’entité indisponible. Sinon, l’absence de lampe allumée impose `off`, puis une session d’édition impose `manual`. Un nom de scène n’est exposé que pour une scène conditionnelle effectivement appliquée ou une scène explicitement lancée pendant sa pause ; une scène dont les conditions sont simplement vraies ne suffit pas. Le lancement explicite peut rester nommé avec l’automatisation désactivée, jusqu’à une nouvelle intervention manuelle ou à la fin de son application.

Hors scène, `natural` exige une application naturelle active et au moins une lampe allumée dans une association concernée. Les autres cas allumés utilisent `manual`, notamment la pause sans scène, le mode automatique désactivé et l’ambiance de base seule. Cette synthèse ne change pas le contrat de statut détaillé envoyé au panneau.

Les attributs `mode`, `scene_id` et `scene_name` permettent de consommer cet état sans dépendre du nom affiché : `mode` vaut `off`, `manual`, `natural` ou `scene` ; les deux attributs de scène valent `null` hors scène. Un nom exactement égal à `off`, `manual`, `natural`, `unknown` ou `unavailable` est préfixé par `scene: ` dans la valeur du capteur pour éviter les traductions des états fixes et les sentinelles Home Assistant. `scene_name` conserve le nom exact dans tous les cas.

Le capteur utilise le contrat officiel de [l’entité Sensor](https://developers.home-assistant.io/docs/core/entity/sensor/) et les [traductions d’états d’entités](https://developers.home-assistant.io/docs/internationalization/core/#state-of-entities). L’ajout n’a pas encore fait l’objet d’un essai navigateur ou domestique.

## Configuration

La configuration regroupe `sun_entity_id`, `transitions`, `profiles` et `rooms`. Les profils sont indexés par identifiant stable. Les pièces sont indexées par identifiant de zone Home Assistant. Les scènes sont une liste ordonnée dans chaque pièce.

Chaque courbe naturelle contient `low_elevation`, `high_elevation`, `low`, `high` et `interpolation`. Les modes proposés sont `linear` et `ease_in_out`. L’ancien identifiant `ease_in` est accepté et normalisé vers `ease_in_out`, y compris pour les courbes du soir masquées, pour appliquer la correction demandée aux profils existants. Pour les courbes actives, l’absence du champ est normalisée en `linear`, sans changement du stockage version 1 ; une valeur inconnue est rejetée. La normalisation seule n’écrit pas, mais une persistance ultérieure de configuration ou de runtime enregistre la valeur canonique. Les autres paramètres du soir ne sont utilisés et validés que lorsque les périodes sont dissociées. Le choix se fait par courbe de luminosité/température et par branche matin/soir, avec le comportement existant de liaison des branches.

Le moteur Python et l’aperçu TypeScript utilisent le même calcul : `t = clamp((elevation - low_elevation) / (high_elevation - low_elevation), 0, 1)`, puis `low + (high - low) × t` en linéaire ou `low + (high - low) × t² × (3 − 2t)` pour la courbe en S (smoothstep). La pente s’annule aux deux bornes. L’ancien identifiant `ease_in` est aussi interprété ainsi par le lecteur et l’aperçu. Les corrections relatives et limites des lampes s’appliquent ensuite. Le temps écoulé n’intervient pas dans cette interpolation : les transitions des commandes restent indépendantes.

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
| `halo/scene/import` | Administrateur | Filtrer et normaliser une configuration de scène Home Assistant en brouillon, sans stockage ni commande matérielle. |
| `halo/edit/begin` | Administrateur | Verrouiller l’édition d’une pièce et obtenir son jeton. |
| `halo/edit/preview` | Administrateur propriétaire | Appliquer l’aperçu aux lampes de la pièce. |
| `halo/edit/touch` | Administrateur propriétaire | Renouveler la session. |
| `halo/edit/end` | Administrateur propriétaire | Enregistrer la scène ou annuler puis libérer l’édition. |

Les permissions Home Assistant filtrent les états lisibles et contrôlent les commandes de lampes. Les erreurs possèdent un code traduit par le panneau, notamment `invalid_config`, `conflict`, `edit_locked` et `invalid_edit`.

### Navigation, brouillon et thème

La refonte compacte ne change aucun contrat WebSocket, REST ni stockage. L’état de navigation du panneau sélectionne les pièces, les profils ou les réglages globaux. Dans une pièce, une sous-vue choisit le pilotage, les lumières, l’automatisation, les ambiances ou les réglages. Les profils ont une sélection distincte et un seul éditeur monté à la fois. La liste de pièces et le détail partagent l’écran sur ordinateur ; la feuille de style affiche successivement ces deux zones sur mobile.

Le brouillon et sa révision restent indépendants des sous-vues. Les champs valides alimentent le modèle dès la saisie. Une entrée numérique invalide est conservée dans le contrôle, sans valeur de remplacement artificielle ; la validation empêche de quitter la sous-vue et focalise le champ. Les sections `details` contenant une erreur sont ouvertes avant sa présentation, y compris pour une condition d’édition. Les bornes solaires sont aussi contrôlées côté panneau. L’abandon utilise une nouvelle clé Lit pour remonter le contenu et effacer les saisies invalides absentes du modèle. Le serveur demeure responsable de la validation complète et des conflits de révision.

Les onglets utilisent les rôles `tablist`, `tab`, `tabpanel`, un seul arrêt de tabulation et les touches fléchées, Début et Fin. La navigation est bloquée pendant une session d’édition réelle. Une annulation d’import redonne le focus au bouton d’import ; sa confirmation cible la nouvelle ligne de scène, car les actions de cette scène ne deviennent disponibles qu’après sauvegarde. La fin d’une édition revient à son bouton de réglage ou à la création d’une scène.

Les styles du panneau et du sélecteur Halo lisent les variables Home Assistant pour les couleurs, états, police, tailles, espacements, bordures, rayons, en-tête et champs. Les valeurs de repli restent locales aux propriétés manquantes ; aucune palette claire/sombre séparée n’est définie par Halo. Le panneau règle `color-scheme` selon `hass.themes.darkMode` lorsqu’il est présent et retire cette surcharge sinon. Les icônes passent par `ha-icon` ; la réduction des mouvements supprime les animations et transitions CSS. Ces choix ne supposent pas le chargement de composants privés de formulaire.

### Import de scènes Home Assistant

Le panneau lit la configuration native par `hass.callApi("GET", "config/scene/config/{id}")`, avec l’identifiant de configuration `attributes.id` encodé comme segment d’URL. Ce n’est pas l’identifiant d’entité `scene.*`. Le frontend officiel utilise [ce même endpoint](https://github.com/home-assistant/frontend/blob/20260930.2/src/data/scene.ts#L147) ; la [vue du cœur](https://github.com/home-assistant/core/blob/2026.10.0/homeassistant/components/config/view.py) contrôle les droits administrateur et lit `scenes.yaml`. Cette dépendance est isolée et vérifiée sur la version prise en charge, sans prétendre à un contrat REST public stable. Aucun accès direct aux fichiers de configuration Home Assistant, objet privé d’intégration ou activation globale de scène n’est nécessaire.

La commande `halo/scene/import` reçoit `room_id` et `config` (configuration native avec `name` et `entities`), et retourne `scene` et `ignored_entities`. Le serveur intersecte les identifiants avec les lampes de la pièce avant de normaliser les valeurs. Une absence de correspondance produit `no_matching_lights` ; un réglage retenu invalide produit `invalid_config`. Les entités extérieures, les domaines autres que `light` et les attributs descriptifs ne deviennent jamais des paramètres de commande. Les groupes ne sont pas développés.

La normalisation suit la [reproduction des états `light` de Home Assistant](https://github.com/home-assistant/core/blob/2026.10.0/homeassistant/components/light/reproduce_state.py) : état simple ou objet, booléens YAML convertis en `on`/`off`, luminosité native et effet, représentation désignée par `color_mode`, ou priorité native en son absence. Le blanc simple utilise la luminosité. Une extinction conserve uniquement `state: off`, sans les anciens attributs de couleur. La validation Halo contrôle ensuite les valeurs reproductibles ; elle n’utilise jamais l’état courant d’une lampe pour remplacer un réglage importé.

Le résultat possède un nouvel identifiant, sans condition et sans autorisation d’allumage automatique. Il est ajouté au brouillon, puis sauvegardé avec `halo/save` et sa révision. La lecture, la normalisation et l’ajout ne commandent aucune lampe. La sauvegarde d’un simple ajout de scènes manuelles n’impose pas de réapplication de l’ambiance. Une copie ne conserve aucune liaison fonctionnelle avec la scène source.

Les scènes sans `id`, absentes de `scenes.yaml` ou fournies par une intégration tierce sans configuration lisible ne sont pas récupérées par activation/capture. Le panneau explique leur indisponibilité et conserve son brouillon en cas d’erreur, de réponse tardive ou de conflit de révision. Une scène native porte souvent un attribut `entity_id` ; cela ne la classe pas parmi les groupes de lampes. Ses références d’entités restent filtrées selon les droits de lecture de l’utilisateur.

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

Les tests Python emploient Home Assistant et son API WebSocket authentifiée avec des lampes simulées. Les 52 tests frontend de la refonte et le contrôle TypeScript réussissent, avec couverture de la navigation, de la conservation des brouillons, de la validation, des droits et du focus. Des essais ciblés d’import et d’édition native ont également été réalisés dans Home Assistant 2026.10.0 isolé. Les preuves, le build et les limites sont décrits dans [DEVELOPMENT.md](DEVELOPMENT.md). Ces vérifications ne remplacent pas l’installation domestique et les essais matériels prévus dans le cahier des charges.
