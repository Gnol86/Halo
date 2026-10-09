# Développer Halo

## Périmètre initial

Le domaine est `halo`. Une première implémentation comprend le moteur d’éclairage, les appareils par pièce, le stockage, l’API et le panneau embarqué. Le comportement attendu est défini dans [PROJET.md](../PROJET.md), les interactions dans [DESIGN.md](../DESIGN.md) et les contrats de code dans [ARCHITECTURE.md](ARCHITECTURE.md). La refonte compacte du panneau suit le thème Home Assistant. Les essais matériels restent à réaliser.

`manifest.json` déclare une intégration de type `service`, une seule entrée de configuration et une classe IoT `calculated` : Halo ne communique pas directement avec un équipement ou un cloud. Réévaluer ces déclarations si le périmètre change.

## Environnement

- Python 3.14.5, compatible avec le minimum Python 3.14.2 de Home Assistant 2026.10.0.
- Home Assistant 2026.10.0 et son environnement de tests figés dans `uv.lock`.
- Frontend officiel Home Assistant 20260930.2 installé comme dépendance de développement pour tester le chargement réel du panneau et de ses dépendances.
- Node.js 24, npm et dépendances TypeScript/Lit figées dans `package-lock.json` pour construire le bundle du panneau.
- `uv sync --frozen` installe l’environnement local dans `.venv/`.
- Les tests utilisent le gestionnaire de configuration réel de Home Assistant et des lumières fictives, sans réseau ni instance domestique.

## Conventions

- Utiliser les API asynchrones de Home Assistant et ses registres d’entités, appareils et pièces.
- Conserver le code distribuable et les ressources nécessaires dans `custom_components/halo/`.
- Ajouter des entités ou actions uniquement lorsqu’un comportement réel est défini.
- Conserver l’état d’exécution futur dans `ConfigEntry.runtime_data` et libérer les abonnements au déchargement.
- Décrire toute future action dans `services.yaml` et traduire ses libellés.
- Mettre les textes de référence dans `strings.json`, et les traductions complètes dans `translations/en.json` et `translations/fr.json`.
- Home Assistant 2026.10 traduit les motifs d’arrêt partagés `single_instance_allowed` et `already_in_progress`. Le motif `already_configured` reste traduit dans Halo.
- Garder la version de développement cohérente entre `manifest.json` et `pyproject.toml` ; une version locale ne constitue pas une release.

## Vérifications

```sh
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
```

Le workflow `Validate` exécute ces contrôles, Hassfest, les tests TypeScript et la cohérence du bundle sur les branches et PR. Il est aussi réutilisé avant publication par `Release`, avec `HACS readiness` sans contrôle ignoré. Le contrôle HACS reste exécutable manuellement et ne publie rien lui-même.

Les tests couvrent la configuration unique, le cycle de vie, le service du bundle, les appareils dynamiques, les décisions du moteur, les profils naturels, les conditions, les transitions, les sessions d’édition, les permissions, la concurrence des écritures et la persistance des pauses. Les lampes et capteurs sont simulés ; l’API WebSocket et les plateformes Home Assistant sont réelles dans l’environnement de test.

Pour le panneau :

```sh
npm ci
npm run check
npm test
npm run build
```

Le bundle dans `custom_components/halo/frontend/` doit rester synchronisé avec `frontend/src/`. Le [guide du panneau](../frontend/README.md) explique l’aperçu local avec données simulées. Un contrôle de types ou un test DOM ne remplace pas un essai intégré dans Home Assistant.

Avant de considérer une version entièrement validée, effectuer également un essai dans une instance Home Assistant de test : installation manuelle, rendu du panneau et du lotus en thèmes clair et sombre, textes français et anglais, pilotage des lampes réelles, redémarrage et suppression. Les tests Python ne valident pas le rendu intégré de l’interface. Les premières releases conservent explicitement ces limites.

## Mise en place des releases GitHub — 9 octobre 2026

Le workflow `Release` valide le tag et les versions du manifeste, de `pyproject.toml` et du verrou uv, puis réutilise les contrôles Python, frontend, Hassfest et HACS avant de publier. Les notes rédigées sont obligatoires. Les formats `vX.Y.ZaN`, `vX.Y.ZbN` et `vX.Y.ZrcN` donnent des préversions ; une relance ne remplace pas une release existante et échoue si celle-ci est encore un brouillon.

- Contrôles locaux : `uv sync --frozen`, Ruff (analyse et format), **324 tests Python réussis**, dont 15 cas du contrôle de publication ; classification comparée à AwesomeVersion, refus des tags invalides, versions divergentes et notes absentes ou vides.
- Sous Node.js 24 : `npm ci`, TypeScript et **55 tests frontend réussis** ; le bundle reconstruit correspond exactement au fichier distribué. Cette tâche ne modifie pas le comportement du panneau.
- La version du projet est `0.1.0`. Le minimum Home Assistant reste `2026.10.0` ; aucune dépendance fonctionnelle n’est mise à jour. La distribution utilise le dossier `custom_components/halo/` du tag et les archives sources natives de GitHub.
- La description et les sujets GitHub ont été renseignés pour satisfaire les métadonnées HACS ; le dépôt est public et les issues sont activées.

La publication distante et ses contrôles seront consignés après leur exécution. Aucun déploiement domestique, essai matériel ou référencement dans le catalogue par défaut n’est effectué par ce workflow.

## Protection de la pause manuelle contre les pertes de présence — 9 octobre 2026

Le même réglage global `presence_return_window` sert aussi à confirmer une absence avant la fin de pause manuelle au retour. La durée minimale est le maximum du délai d’absence de la pièce et de cette protection globale ; zéro conserve le seul délai de la pièce. Cette règle s’applique à toutes les pièces, indépendamment de l’extinction sur luminosité. Elle ne change ni la temporisation d’extinction ni l’expiration propre de la pause ou le bouton de reprise.

- `uv sync --frozen`, Ruff (analyse et format) et **309 tests Python réussis**. Les **33 nouveaux scénarios** couvrent le défaut de 30 secondes, zéro, les bornes exactes, les délais locaux plus longs, les deux politiques d’extinction pendant la pause et les deux réglages d’extinction sur luminosité.
- Présence personnalisée, mises à jour d’attributs, indisponibilité interrompant l’absence continue, scène manuelle conservée après une courte absence, expiration normale, reprise et rechargement sont testés. Un ancien marqueur `absence_confirmed` ne suffit plus à effacer une pause : la durée observée est recontrôlée.
- Un service d’extinction bloqué vérifie qu’un retour reçu après une seconde conserve la pause même si le moteur attend plus de 30 secondes pour reprendre : l’heure du premier retour, et non celle de libération du verrou ou d’un changement entre états « présents », sert à la décision. Plusieurs pertes brèves pendant cette attente ne sont pas additionnées.
- Sous Node.js 24 : `npm ci`, TypeScript, **55 tests frontend réussis** et bundle reconstruit à l’identique. SHA-256 : `63edac26052f1c1c1acc174a9df222bb143d6aa61311b4561ecbc749695ff47c`. Le champ est désormais intitulé « Délai de protection de présence (secondes) » ; l’aide française/anglaise dépliable précise les deux usages et leurs périmètres.

Vérifications automatisées locales avec capteurs et lampes simulés ; aucun nouvel essai visuel intégré, essai matériel ou déploiement domestique pour cette extension. Les documents produit, design, README et architecture reflètent ce comportement.

## Rallumage rapide après une perte de présence — 9 octobre 2026

Le réglage global `presence_return_window` vaut initialement 30 secondes, y compris pour une configuration ancienne sans ce champ ; zéro désactive la protection. Dans les pièces sans extinction sur forte luminosité, un véritable retour de présence pendant cette fenêtre après une extinction pour absence force l’ambiance applicable avec la transition `turn_on`, sans attendre le capteur lumineux. La fenêtre est temporaire, consommée une seule fois et annulée par les interventions manuelles, l’édition, la désactivation ou une reconfiguration.

- `uv sync --frozen`, analyse et formatage Ruff conformes ; **276 tests Python réussis** dans l’environnement Home Assistant 2026.10.0, avec lampes et capteurs simulés.
- Les nouveaux scénarios couvrent la limite stricte, zéro, les états de présence personnalisés et indisponibles, le départ de la fenêtre à la première commande d’extinction pour absence plutôt qu’au début de l’absence, les pauses, les scènes et profils naturels, l’hystérésis conservée et l’absence de second allumage après publication lumineuse tardive.
- Le retour pendant un fondu est simulé avec des lampes se déclarant encore allumées ; un service d’extinction bloqué vérifie l’invalidation des autres extinctions en attente et la priorité d’une nouvelle commande manuelle. Les annulations et l’absence de restauration après redémarrage sont également couvertes.
- Les tests API vérifient le défaut historique, les valeurs explicites dont zéro et les décimales, la sauvegarde/relecture/recharge, le conflit de révision et le rejet atomique d’une valeur invalide, sans commande aux lampes.
- Sous Node.js 24 : `npm ci`, TypeScript et **55 tests frontend réussis**. Le champ obligatoire accepte de 0 à 604 800 secondes ; validation des valeurs non finies, traductions anglaises/françaises, brouillon, sauvegarde, abandon et droits administrateur sont couverts.
- Bundle reconstruit deux fois à l’identique : SHA-256 `0ab87972202db015f17770bc3850abcfa1c0942bc669af34009d9d0ec56dcfcf`. Documents produit, design, README et architecture synchronisés.

Ces vérifications automatisées locales ne constituent pas un nouvel essai visuel dans Home Assistant ni une validation matérielle. Aucun déploiement domestique ou commande aux équipements réels n’a été effectué pour cet ajout.

## Filtre des lumières des autres pièces — 9 octobre 2026

L’onglet Lumières masque par défaut les lampes extérieures non sélectionnées. Une case permet de les afficher, y compris celles sans pièce ; les lampes extérieures déjà sélectionnées restent dans un groupe distinct. Ce filtre est temporaire et ne modifie pas la configuration.

- Installation npm, contrôle TypeScript et **55 tests frontend réussis** sous Node.js 24 ; bundle reconstruit.
- Vérification DOM ciblée avec données simulées : affichage initial, recherche limitée à la liste visible, ouverture/fermeture, lampes sans pièce ou indisponibles, affectation à une autre pièce verrouillée, absence de brouillon et d’appel de sauvegarde pour le filtre seul, sélection conservée au masquage, abandon, changement de pièce et remontage du panneau.
- Aucun changement du moteur ni de l’API ; aucun essai sur l’instance domestique pour cet ajout.

## Capteur d’état par pièce — 9 octobre 2026

Chaque appareil de pièce comprend maintenant un capteur `Status` / `État`. Il expose `off`, `manual`, `natural` avec traductions natives ou le nom de la scène active ; les attributs `mode`, `scene_id` et `scene_name` permettent d’identifier une scène indépendamment de son nom. Les lampes réellement éteintes et leur indisponibilité priment sur le mode d’éclairage. Cet ajout ne modifie pas les décisions du moteur ni les commandes aux lampes.

- `uv sync --frozen`, Ruff (analyse et format) et **232 tests Python réussis** dans l’environnement Home Assistant 2026.10.0, avec lampes simulées.
- Nouveaux cas : transitions naturel/scène/manuel/éteint, scène simplement sélectionnée, scène explicite avec effet et pause conservée après redémarrage, édition, pause nulle, capteur amont indisponible, lampes indisponibles puis disponibles, renommages, cycle de vie des entités et traductions anglaises/françaises. Les noms de scène correspondant aux états réservés sont également couverts.
- Les tests de plateformes et du gestionnaire vérifient l’ajout au même appareil, la mise à jour événementielle sans panneau, le rechargement avec identité conservée et le retrait des entités.
- Aucun changement frontend pour cet ajout ; le bundle et le tri des pièces issus de la tâche précédente sont conservés. Aucun nouvel essai navigateur, déploiement domestique ni commande sur du matériel réel n’a été effectué pour ce capteur.

## Refonte compacte du dashboard — 9 octobre 2026

La navigation adopte une liste de pièces et un panneau de détail, avec pilotage prioritaire, cinq rubriques par pièce et un éditeur de profil naturel à la fois. Sur mobile, la liste et le détail se succèdent. Le moteur, le stockage et les contrats API restent inchangés.

- `uv sync --frozen`, Ruff (analyse et format), TypeScript et installation npm réussis ; **219 tests Python et 52 tests frontend réussis**. Les nouveaux cas couvrent la navigation clavier/ARIA, les brouillons entre vues, les erreurs de saisie avant navigation, les droits, le verrouillage d’édition et le changement de thème Home Assistant à chaud.
- Aperçu isolé avec données simulées : pilotage et profils examinés à **1436 pixels** de large et **390 × 844**, thèmes clair et sombre ; thème personnalisé avec police, espacements et rayons différents, texte à **125 %**. Les valeurs calculées confirment l’héritage de ces variables et aucun débordement horizontal n’est relevé dans la vue des réglages globaux à 390 pixels. Les onglets de pièce défilent horizontalement sur petit écran.
- **Home Assistant 2026.10.0 isolé**, frontend **20260930.2**, lampes simulées : ouverture de la scène partielle existante avec deux lampes incluses sur quatre, ouverture de la fenêtre native de lampe avec effet `Candle` visible, puis annulation et sortie de session vérifiées. L’import de la source native affiche deux lampes retenues et deux entités ignorées ; ajout au brouillon et abandon vérifiés. Aucune erreur console constatée durant ce parcours. Ce passage ne répète pas les essais matériels ni toute la validation de l’import du jalon précédent.
- Les variables d’interface sont héritées, avec repli lorsque la variable manque. Les [variables de thème documentées](https://www.home-assistant.io/integrations/frontend/#supported-theme-variables) sont complétées par les propriétés présentes dans les sources du frontend pris en charge : [couleurs](https://github.com/home-assistant/frontend/blob/20260930.2/src/resources/theme/color/color.globals.ts), [typographie](https://github.com/home-assistant/frontend/blob/20260930.2/src/resources/theme/typography.globals.ts), [espacements et rayons](https://github.com/home-assistant/frontend/blob/20260930.2/src/resources/theme/core.globals.ts). Ces propriétés supplémentaires ne sont pas présentées comme un contrat public stable. Un thème tiers arbitraire peut toujours définir des contrastes insuffisants.
- Revue visuelle Impeccable séparée : structure, thème, captures et parcours conformes ; une ambiguïté du message de brouillon a été corrigée. Le verdict `ship` du second passage porte sur cette correction : les commandes explicites restent utilisables pour une pièce enregistrée, tandis que les modes et la reprise attendent la sauvegarde ou l’abandon. Une nouvelle pièce doit être enregistrée avant le pilotage.
- Serveurs et onglets de test fermés, ports locaux vérifiés fermés. Le harness Home Assistant conserve son code de sortie `139` après SIGTERM et l’avertissement caméra `libturbojpeg` déjà documentés ; l’arrêt normal du harness n’est pas validé par ce passage.
- Captures de revue locales dans `.impeccable/review/` (ignoré par Git). Le bundle distribué est reconstruit et sa reproductibilité vérifiée. Cette vérification locale ne constitue ni un push, ni une activation sur l’instance domestique.

## Import de scènes Home Assistant — 9 octobre 2026

L’import utilise la lecture REST du cœur employée par l’éditeur natif, puis la normalisation administrateur `halo/scene/import`. Il crée une copie indépendante dans le brouillon de la pièce. Les lampes non incluses restent inchangées au lancement ; les cases d’inclusion et `capture_entities` préservent cette sélection à la réédition.

- **219 tests Python et 43 tests frontend réussis**, synchronisation uv, installation npm, Ruff et TypeScript conformes. Couverture du filtrage exact, droits, booléens YAML, états éteints, effets, couleurs natives et RGBW/RGBWW, indisponibilités, sélection partielle, concurrence, réponses tardives, annulation et conflits. L’ajout et la sauvegarde de scènes manuelles seuls ne forcent pas de commande, même avec les automatismes activés.
- Parcours dans une **instance Home Assistant 2026.10.0 isolée**, frontend officiel **20260930.2**, cinq lampes simulées : la source comporte deux lampes de la pièce, une extérieure et une autre entité. L’aperçu affiche **deux lampes retenues et deux entités ignorées**. Renommer la copie en « Lecture Halo », confirmer puis enregistrer laisse tous les compteurs de commandes à zéro. Le fichier source reste inchangé.
- Le lancement de la copie puis sa réouverture et son enregistrement n’envoient des commandes qu’aux deux lampes retenues. Le stockage conserve `Candle`, la luminosité `191` et la température `2700 K` pour la première, la luminosité `112` et RGBW `[200, 60, 10, 44]` pour la seconde. Les deux autres lampes de la pièce et celle extérieure restent inchangées, compteurs à zéro. Les cases d’inclusion reflètent exactement les deux membres.
- Source sans identifiant et absence de lampe commune : messages explicites et confirmation désactivée dans le panneau. Source introuvable : HTTP 404 vérifié via l’API. Une copie non enregistrée est ajoutée en dernière position, avec son nom saisi, puis supprimée par l’abandon du brouillon ; son lancement reste désactivé jusqu’à la sauvegarde.
- Après redémarrage de l’instance isolée, la configuration et la copie enregistrée restent identiques. La vérification a également corrigé une confusion entre les références `entity_id` des scènes natives et les groupes de lampes ; les permissions de lecture restent appliquées.
- Formulaire examiné en français à la taille habituelle et à **375 × 812** / **768 × 1024** : champs et actions accessibles par défilement, sans débordement horizontal observé. Les cas anglais/français et la parité des catalogues sont couverts par les tests frontend. Captures et preuves API conservées dans le répertoire local ignoré `tmp/`.
- Bundle reconstruit sous Node.js 24 et reproduction à l’identique vérifiée. `PROJET.md`, `DESIGN.md`, `README.md` et les contrats techniques actualisés.
- Instance et onglet de test fermés, port local vérifié fermé. Le harness retourne encore `139` après son arrêt, sans nouveau traceback Halo ; sa fermeture normale n’est donc pas confirmée.

La compatibilité vérifiée concerne les scènes lisibles dans `scenes.yaml` avec un identifiant. Cette API du cœur n’est pas un contrat public stable. Aucun déploiement dans le logement ni commande aux équipements réels ; leur validation reste à faire.

## Courbes en S et étude des sélecteurs natifs — 9 octobre 2026

Le retour sur l’accélération progressive remplace la courbe quadratique initiale par `t²(3 − 2t)` : départ doux, accélération au milieu, décélération à l’arrivée. Le mode canonique est `ease_in_out`. Les anciens `ease_in` sont normalisés, y compris les branches du soir masquées ; la normalisation n’écrit pas directement dans le stockage. Une persistance ultérieure de configuration ou de runtime peut conserver le nouvel identifiant.

- **172 tests Python et 34 tests frontend réussis**, Ruff et TypeScript conformes. Parité des calculs, quarts/milieu/bornes, valeurs croissantes ou décroissantes, compatibilité historique et indépendance des transitions vérifiées.
- Aperçu isolé en navigateur avec données simulées : sélection « Accélération et décélération » pour luminosité et température, deux courbes en S raccordées aux plateaux, seuils décimaux conservés et choix maintenus après sauvegarde. Cet essai des courbes n’utilise pas l’instance domestique.
- Bundle reconstruit et cohérence documentaire vérifiée. Les tests de l’édition native des scènes restent inclus dans les résultats ci-dessus.
- Sélecteurs d’entités natifs : recherche documentaire et lecture des sources officielles réalisées. Aucun mécanisme public de chargement dans le panneau identifié ; remplacement **non implémenté**, conformément à la contrainte de ne pas introduire de chargement fragile. Voir le [diagnostic détaillé](ARCHITECTURE.md#sélecteurs-dentités-natifs).

## Édition native des scènes et effets — 9 octobre 2026

Le panneau ouvre la vraie fenêtre de contrôle d’une lampe avec l’action publique `hass-action` / `more-info`. La liste reste dans Halo. Aucune copie de composant privé ni interception des commandes du frontend n’est utilisée. Les sources officielles étudiées et la distinction avec la distribution HACS sont consignées dans [ARCHITECTURE.md](ARCHITECTURE.md#contrôles-natifs-des-lampes-dans-les-scènes).

- **168 tests Python réussis**, avec une limite de 45 secondes par test ; synchronisation uv, Ruff et formatage conformes. Capture au moment du commit sous verrou, droits et propriétaire, révision, conservation après rechargement et rappel, effets, luminosité native, RGBW/RGBWW, blanc simple, annulation/expiration et indisponibilités couverts.
- **33 tests frontend réussis**, TypeScript conforme. Événement public, attente de l’aperçu initial, sauvegarde avec capture serveur sans aperçu périmé, état/effet réel, traductions, expiration et fermeture pendant l’ouverture de session couverts.
- Essai dans une **instance Home Assistant 2026.10.0 isolée sur la boucle locale**, avec son **frontend officiel 20260930.2** et quatre entités `LightEntity` simulées. Arrivée directe sur `/halo`, sans ouverture préalable de Lovelace ; clic ouvrant la fenêtre native, sélection de l’effet `Candle`, retour visible dans Halo et sauvegarde vérifiés. Le stockage contient la luminosité native `153`, l’effet `Candle`, la température `3200 K`, les canaux RGBW/RGBWW des autres lampes et le mode blanc simple.
- Une nouvelle édition remplace temporairement `Candle` par `Rainbow` ; **Annuler** restaure `Candle / 153 / 3200 K`. L’API confirme ensuite `editing=false`, automatismes toujours désactivés et aucune erreur de pièce.
- Après une commande officielle de test passant la lampe à l’effet `None` et à la luminosité `80`, **Lancer** dans Halo restaure `Candle / 153 / 3200 K`, les valeurs RGBW/RGBWW et le mode blanc. Aucune erreur Halo ajoutée aux journaux pendant ce parcours.
- Le démarrage du harness a d’abord échoué sur les descriptions d’actions HA (`get_services`, dépendance `hassil` absente). Les dépendances officielles nécessaires ont été ajoutées dans un dossier temporaire isolé, sans changer le runtime ni les fichiers de dépendances du projet. Le parcours décrit ci-dessus utilise les composants officiels, sans simuler la fenêtre native.
- Bundle reconstruit sous Node.js 24 et reproduction à l’identique vérifiée ; documentation produit, design, README et contrat API synchronisés. Le simulateur HTML signale explicitement qu’il ne fournit pas la fenêtre Home Assistant.
- Instance de test arrêtée, port fermé et onglet temporaire fermé. Le processus du harness a retourné le code `139` après `SIGTERM`, sans nouveau diagnostic dans le journal ; l’arrêt effectif est confirmé, sa fermeture normale ne l’est pas.

Pas de déploiement dans le logement ni de commande aux lampes réelles. La conservation concerne les réglages reproductibles remontés par chaque intégration `light`, pas ses fonctions propriétaires absentes de l’état Home Assistant.

## Types de courbes naturelles — 9 octobre 2026

Historique de la première version, remplacée depuis par la correction en S décrite plus haut.

Chaque courbe de luminosité et de température dispose d’un choix entre linéaire et accélération progressive quadratique. Le moteur et l’aperçu utilisent la même progression selon la hauteur solaire ; les transitions en secondes restent indépendantes. Les anciens profils sans choix explicite restent linéaires.

- **132 tests Python réussis**, avec une limite de 45 secondes par test ; synchronisation uv, analyse et formatage Ruff conformes. Les nouveaux cas vérifient les calculs, les pentes croissantes/décroissantes, les plateaux, les modes indépendants, les offsets, les commandes aux lampes simulées et la conservation des modes après sauvegarde/rechargement. Le chargement d’un ancien profil ne réécrit pas le stockage ; les modes invalides sont rejetés sans modifier la configuration.
- **28 tests frontend réussis** et TypeScript conforme : choix par courbe, indépendance des périodes dissociées, parité des traductions, courbes historiques, rendu du mode progressif et sauvegarde des sélections couverts.
- Aperçu local en navigateur avec données simulées : passage de la luminosité à « Accélération progressive », température conservée en « Linéaire », courbe transformée immédiatement, graduations aux seuils conservées et sélection maintenue après enregistrement. Aucun appel à l’instance domestique.
- Bundle reconstruit sous Node.js 24 ; reproduction du bundle vérifiée. `PROJET.md`, `DESIGN.md`, `README.md` et le contrat d’architecture actualisés.

Fonction implémentée et vérifiée localement, pas déployée dans Home Assistant par cette tâche. Les essais sur les lampes réelles restent à réaliser.

## Barre d’enregistrement, graphiques et groupes Hue — 9 octobre 2026

Les nouveaux retours du panneau sont corrigés dans le dépôt. Une lecture du DOM de l’instance domestique a confirmé que la hauteur du panneau suivait le contenu (2 379 px pour une fenêtre de 1 264 px), empêchant la barre de rester au bas de la fenêtre. Le panneau utilise désormais la hauteur dynamique de la fenêtre et une zone de contenu défilante distincte des actions.

- **112 tests Python réussis**, avec une limite de 45 secondes par test ; synchronisation uv et contrôles Ruff conformes. Les nouveaux cas couvrent les groupes Hue sans membres, les ensembles de membres, les permissions et les métadonnées conservées lorsqu’un groupe est indisponible.
- **25 tests frontend réussis** et TypeScript conforme. Le nouveau test des graphiques couvre les seuils saisis, leurs positions exactes, les décimales proches, les limites ±90°, les courbes descendantes et constantes.
- Aperçu local avec données simulées aux tailles **1 436 × 1 264**, **768 × 1 024** et **375 × 812** : barre visible en bas pendant le défilement, contenu accessible sans recouvrement ni débordement horizontal observé. Les actions mobiles sont alignées côte à côte sous le message.
- Repères **−6° / 45°** examinés sur la courbe et seuils décimaux conservés ; champs globaux alignés, y compris après passage sur plusieurs rangées. Sélecteurs et durées par pièce alignés avec un mélange des modes durée, héritage et absence de transition. Français/anglais et thèmes clair/sombre examinés.
- Bundle reconstruit sous Node.js 24. La correction concerne aussi le format des membres Hue v2 (`set`) et le marqueur des groupes Hue v1 (`is_hue_group`), confirmés dans les sources Home Assistant 2026.10 : [Hue v2](https://github.com/home-assistant/core/blob/2026.10.0/homeassistant/components/hue/v2/group.py) et [Hue v1](https://github.com/home-assistant/core/blob/2026.10.0/homeassistant/components/hue/v1/light.py).

Ces corrections ne sont pas déployées par cette tâche. Le cas réel `light.bureau_2` devra être vérifié après installation ; aucune commande aux lampes et aucune modification de la configuration domestique n’ont été effectuées. Les contrôles visuels ci-dessus utilisent l’aperçu simulé, pas le panneau corrigé dans Home Assistant.

## Menu et lotus du panneau — 9 octobre 2026

Le bouton de menu ajouté par Halo est retiré. La barre latérale et l’en-tête utilisent désormais `mdi:spa`, le lotus monochrome du catalogue natif Home Assistant. L’ancien identifiant `mdi:flower-lotus` n’existe pas dans ce catalogue. Le nom est confirmé par la [fiche officielle de l’icône](https://pictogrammers.com/library/mdi/icon/spa/) et par sa présence dans Material Design Icons 7.4.47, embarqué par le frontend Home Assistant 20260930.2.

- TypeScript conforme ; **24 tests frontend réussis**.
- Synchronisation uv et Ruff conformes ; **105 tests Python réussis** avec une limite de 45 secondes par test. Une première exécution a été interrompue après 65 tests réussis, pendant le test HTTP du bundle ; les deux tests de cycle de vie/service HTTP, les 39 tests restants puis la suite complète ont réussi à la relance. Le blocage initial n’a pas été reproduit.
- Bundle reconstruit avec Node.js 24 et reproductibilité vérifiée sur deux compilations. L’ancien identifiant et le bouton de menu sont absents du bundle.
- Documentation fonctionnelle, design, README et distinction entre icône latérale et images HACS actualisés.
- Correctif local, pas encore déployé dans le logement ; son rendu intégré dans Home Assistant reste à vérifier après installation.

## Retours du panneau et corrections — 9 octobre 2026

Les annotations et la lecture du panneau domestique confirment son ouverture dans Home Assistant. Cette observation ne vaut pas validation des automatismes ou des lampes réelles. Les corrections ci-dessous sont préparées dans le dépôt ; elles n’ont pas été déployées sur cette instance pendant cette tâche.

- Tests Python : **105 réussis** ; synchronisation uv, analyse et formatage Ruff conformes. Les nouveaux cas vérifient les valeurs initiales, la conservation des réglages historiques au rechargement et les métadonnées de groupes filtrées par droits de lecture.
- Tests frontend : **24 réussis**, avec TypeScript conforme. Recherche par nom/identifiant sans casse ni accents, sélection au clavier, conservation de la recherche et des valeurs, annulation, effacement, indisponibilité, filtrage des domaines, validation des conditions et catalogue de 240 entités couverts.
- Création de profils et de scènes vérifiée dans les tests avec `crypto.randomUUID` absent ; le remplacement utilise `getRandomValues`. L’URL HTTP de ces tests DOM et l’absence simulée de cette API ne constituent pas un essai sur l’instance domestique.
- Unités `%`, `lx` et absence d’unité testées sans conversion des seuils ; indication des groupes et préservation des lampes masquées par une recherche vérifiées.
- Aperçu isolé dans le navigateur : groupes/membres visibles, recherche sans accents, sélection à la souris et au clavier, passage d’un capteur `lx` à `%`, absence à 0 seconde, pause à 120 minutes, valeurs des cinq transitions et création d’un profil examinés. Les données sont simulées, sans commande au logement.
- Bundle reconstruit avec Node.js 24 ; une seconde compilation produit le même SHA-256. Les valeurs existantes de l’instance et la saisie non enregistrée du panneau utilisateur sont préservées.

## Vérifications de la première implémentation — 9 octobre 2026

- Tests Python : **99 réussis**, avec Home Assistant 2026.10.0 et des lampes/capteurs simulés.
- Ruff : analyse et formatage conformes.
- Hassfest : **1 intégration, 0 invalide**, exécuté localement avec les mêmes sources officielles que lors de l’initialisation, sans contrôle ignoré.
- API : contrôles d’accès, conflits de révision, verrou d’édition entre connexions, sauvegarde, restauration et abonnement après rechargement testés.
- Panneau : contrôle TypeScript et bundle local construits ; aperçu dans Chrome avec données simulées en français/anglais, clair/sombre et à 375 × 812. Aucun débordement horizontal sur les vues examinées.
- Tests frontend : **16 réussis**, couvrant également les sélections de formulaires, la conservation de la saisie pendant les mises à jour, la reconnexion et l’ordre des aperçus avant enregistrement ou annulation.
- Non vérifiés : installation du nouveau panneau dans une instance domestique, rendu intégré avec tous les thèmes Home Assistant et comportement des lampes réelles.

Sans contexte restitué par la lampe, une intervention physique produisant exactement la même progression qu’une transition attendue ne peut pas être distinguée avec certitude. Ce comportement et les capteurs lumineux exposés aux lampes nécessitent une validation sur les équipements cibles.

La publication HACS reste un jalon futur. Les vérifications ci-dessus n’ont installé ni activé Halo dans le logement.

## Vérifications de l’initialisation — 9 octobre 2026

- Ruff : analyse et formatage réussis.
- Tests : **4 réussis**, avec Home Assistant 2026.10.0 sous Python 3.14.5.
- Hassfest : **1 intégration, 0 invalide**, avec le code officiel du tag `2026.10.0` (`6a811d3359c7b2076dc9e1cf900843a129c044af`), sans contrôle ignoré. Exécuté localement depuis les sources ; la dépendance de validation `infrared-protocols==10.1.0` était fournie dans un environnement temporaire uv, sans ajout aux dépendances de Halo.
- Icônes : PNG RGBA avec transparence réelle, dimensions 256 × 256 et 512 × 512 vérifiées.
- Métadonnées : JSON, cohérence des versions, traduction anglaise et syntaxe YAML des workflows vérifiés.
- Non exécutés : workflows distants GitHub, validation HACS du dépôt distant et essai visuel dans une instance Home Assistant. La description et les sujets GitHub restent à compléter au jalon final.

Ces résultats concernent le socle présent, pas les futures fonctions d’éclairage. Aucun push, tag, release ni demande d’inclusion HACS n’a été effectué pendant cette initialisation.

## Références

- [Structure d’une intégration](https://developers.home-assistant.io/docs/creating_integration_file_structure/)
- [Manifeste](https://developers.home-assistant.io/docs/creating_integration_manifest/)
- [Config flow](https://developers.home-assistant.io/docs/core/integration/config_flow/)
- [Traduction centralisée des motifs d’arrêt](https://developers.home-assistant.io/blog/2026/09/28/central-config-flow-abort-reasons/)
- [Hassfest](https://developers.home-assistant.io/blog/2020/04/16/hassfest/)
