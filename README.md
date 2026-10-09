<p align="center">
  <img src="custom_components/halo/brand/icon@2x.png" alt="Lotus de Halo" width="144" height="144">
</p>

# Halo

Une intégration Home Assistant destinée à gérer l’ensemble des lumières du logement.

**Statut : socle de développement.** Halo peut être ajouté dans l’interface de Home Assistant, mais ne pilote encore aucune lumière et ne fournit pas encore de dashboard. Le cahier des charges fonctionnel est défini ; son implémentation reste à réaliser. La publication et le référencement dans HACS sont prévus à la fin du projet.

## Ce qui existe

- Structure d’une intégration personnalisée dans `custom_components/halo/`.
- Configuration depuis l’interface, avec une seule instance par logement.
- Chargement, déchargement et rechargement de l’intégration.
- Textes en français et en anglais, icône de lotus embarquée.
- Tests avec Home Assistant et workflows de validation préparés.

## Fonctionnalités prévues — à développer

Les comportements retenus sont détaillés dans [PROJET.md](PROJET.md), et les règles d’interface dans [DESIGN.md](DESIGN.md). Aucune des fonctions suivantes n’est encore disponible :

- Un panneau **Halo** ajouté automatiquement à la barre latérale après l’installation unique, pour toute la configuration ; pilotage accessible aux utilisateurs et configuration réservée aux administrateurs.
- Les pièces de Home Assistant, avec sélection explicite des lumières et un appareil par pièce regroupant la commande d’éclairage, les modes automatique et naturel, la reprise et les scènes.
- L’allumage et l’extinction selon la présence et la luminosité, avec seuil, hystérésis et temporisations configurables.
- Une pause après une commande manuelle, avec une option par pièce pour maintenir les extinctions automatiques pendant cette pause.
- Des profils de lumière naturelle fondés sur l’élévation du soleil, associables à plusieurs groupes dans une même pièce, avec courbes de luminosité et de température de blanc adaptées aux lampes compatibles.
- Une ambiance de base et des scènes conditionnelles prioritaires, ordonnées dans le dashboard, avec édition en direct sur les lampes pendant la suspension de l’automatisation de la pièce.
- Des transitions par type de changement, définies globalement et personnalisables ou désactivables par pièce.
- L’anglais comme langue de référence, une traduction française suivant la langue de l’interface Home Assistant et un repli en anglais pour les autres langues. Les noms personnalisés restent inchangés.

Les choix esthétiques du dashboard restent à définir. Les étapes d’implémentation et de validation figurent dans la [feuille de route](docs/ROADMAP.md).

## Essai manuel en développement

La version de référence et le minimum déclaré sont **Home Assistant 2026.10.0**. La compatibilité avec les versions précédentes n’est pas revendiquée.

1. Copier le dossier `custom_components/halo` dans le dossier `custom_components` de la configuration d’une instance de test Home Assistant.
2. Redémarrer cette instance pour qu’elle découvre les fichiers.
3. Ouvrir **Paramètres → Appareils et services → Ajouter une intégration**.
4. Rechercher **Halo**, puis confirmer la configuration.

Cette étape crée seulement l’entrée d’intégration. Il est normal de ne voir aucune nouvelle entité ni action. Pour la retirer, supprimer son entrée dans **Appareils et services**, puis son dossier si nécessaire.

## Développement

Avec [uv](https://docs.astral.sh/uv/) installé :

```sh
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
```

Le fichier `.python-version` fixe Python 3.14.5 ; `uv.lock` fixe les dépendances des tests. Aucune dépendance Python externe n’est requise par Halo dans l’instance Home Assistant.

Ce README, `PROJET.md` et `DESIGN.md` sont maintenus à jour en temps réel. Toute évolution doit être répercutée dans les documents concernés au cours de la même tâche, selon les consignes d’`AGENTS.md`.

- [Consignes pour les agents](AGENTS.md)
- [Projet et fonctionnalités](PROJET.md)
- [Design du dashboard](DESIGN.md)
- [Conventions de développement](docs/DEVELOPMENT.md)
- [Documentation HACS étudiée et publication future](docs/HACS.md)
- [Feuille de route](docs/ROADMAP.md)
- [Icône et source graphique](assets/branding/README.md)

## Licence

[MIT](LICENSE).
