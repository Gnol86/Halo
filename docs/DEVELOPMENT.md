# Développer Halo

## Périmètre initial

Le domaine est `halo`. Une première implémentation comprend le moteur d’éclairage, les appareils par pièce, le stockage, l’API et le panneau embarqué. Le comportement attendu est défini dans [PROJET.md](../PROJET.md), les interactions dans [DESIGN.md](../DESIGN.md) et les contrats de code dans [ARCHITECTURE.md](ARCHITECTURE.md). Les essais matériels et les choix esthétiques définitifs restent à réaliser.

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

Le workflow `Validate` prépare ces contrôles, Hassfest, les tests TypeScript et la cohérence du bundle pour les futurs pushes et PR. `HACS readiness` s’exécute uniquement à la demande et ne publie rien. Son succès dépend aussi des métadonnées GitHub, à compléter au jalon de publication.

Les tests couvrent la configuration unique, le cycle de vie, le service du bundle, les appareils dynamiques, les décisions du moteur, les profils naturels, les conditions, les transitions, les sessions d’édition, les permissions, la concurrence des écritures et la persistance des pauses. Les lampes et capteurs sont simulés ; l’API WebSocket et les plateformes Home Assistant sont réelles dans l’environnement de test.

Pour le panneau :

```sh
npm ci
npm run check
npm test
npm run build
```

Le bundle dans `custom_components/halo/frontend/` doit rester synchronisé avec `frontend/src/`. Le [guide du panneau](../frontend/README.md) explique l’aperçu local avec données simulées. Un contrôle de types ou un test DOM ne remplace pas un essai intégré dans Home Assistant.

Avant une release utilisable, effectuer également un essai dans une instance Home Assistant de test : installation manuelle, rendu du panneau et du lotus en thèmes clair et sombre, textes français et anglais, pilotage des lampes réelles, redémarrage et suppression. Les tests Python ne valident pas le rendu intégré de l’interface.

## Types de courbes naturelles — 9 octobre 2026

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
