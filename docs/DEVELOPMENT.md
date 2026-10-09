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
