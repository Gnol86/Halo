# Développer Halo

## Périmètre initial

Le domaine est `halo`. L’intégration expose pour l’instant un parcours de configuration et un cycle de vie sans logique d’éclairage. Les futures fonctions s’appuieront sur les lumières déjà connues de Home Assistant. Leur comportement et l’architecture retenue sont définis dans [PROJET.md](../PROJET.md), et les interactions du panneau dans [DESIGN.md](../DESIGN.md). Ces fonctions restent à développer ; les choix esthétiques du dashboard restent à définir.

`manifest.json` déclare une intégration de type `service`, une seule entrée de configuration et une classe IoT `calculated` : Halo ne communique pas directement avec un équipement ou un cloud. Réévaluer ces déclarations si le périmètre change.

## Environnement

- Python 3.14.5, compatible avec le minimum Python 3.14.2 de Home Assistant 2026.10.0.
- Home Assistant 2026.10.0 et son environnement de tests figés dans `uv.lock`.
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

Le workflow `Validate` prépare ces contrôles et Hassfest pour les futurs pushes et PR. `HACS readiness` s’exécute uniquement à la demande et ne publie rien. Son succès dépend aussi des métadonnées GitHub, à compléter au jalon de publication.

Les tests couvrent la confirmation de création, le refus d’une seconde instance, deux configurations simultanées et le cycle chargement/déchargement/rechargement/suppression.

Avant la première version fonctionnelle, effectuer également un essai dans une instance Home Assistant de test : installation manuelle, affichage du lotus en thèmes clair et sombre, textes français et anglais, redémarrage, suppression. Les tests Python ne valident pas le rendu de l’interface.

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
