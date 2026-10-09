<p align="center">
  <img src="https://raw.githubusercontent.com/Gnol86/Halo/main/custom_components/halo/brand/icon@2x.png" alt="Lotus de Halo" width="144" height="144">
</p>

# Halo

Une intégration Home Assistant destinée à gérer l’ensemble des lumières du logement.

**Statut : première version de développement.** Halo dispose d’un panneau embarqué, d’appareils par pièce et d’un moteur d’éclairage. Les vérifications locales utilisent Home Assistant avec des lampes simulées et un navigateur avec des données simulées. Les premiers retours du panneau dans Home Assistant sont pris en compte ; la validation complète dans une instance domestique et avec des lampes réelles reste à réaliser. La publication et le référencement dans HACS sont prévus à la fin du projet.

## Ce qui existe

- Structure d’une intégration personnalisée dans `custom_components/halo/`.
- Configuration depuis l’interface, avec une seule instance par logement.
- Chargement, déchargement et rechargement de l’intégration.
- Textes en français et en anglais, icône de lotus embarquée.
- Tests avec Home Assistant et workflows de validation préparés.

**Icône dans HACS :** HACS 2.0.5 affiche encore une image de remplacement dans sa liste pour les nouvelles intégrations comme Halo. Les fichiers du lotus sont bien embarqués pour Home Assistant ; l’image de présentation de ce README utilise une URL absolue indépendante de cette limite. Le [diagnostic et le correctif attendu côté HACS](docs/HACS.md#affichage-du-lotus) sont documentés.

## Première implémentation fonctionnelle

Les comportements retenus sont détaillés dans [PROJET.md](PROJET.md), et les règles d’interface dans [DESIGN.md](DESIGN.md). Le code et le panneau comprennent maintenant :

- Un panneau **Halo** ajouté automatiquement à la barre latérale après l’installation unique, pour toute la configuration ; pilotage accessible aux utilisateurs et configuration réservée aux administrateurs.
- Un lotus monochrome natif dans la barre latérale et l’en-tête, suivant le thème Home Assistant ; l’en-tête Halo ne comporte pas de bouton de menu supplémentaire.
- Les pièces de Home Assistant, avec sélection explicite des lumières et un appareil par pièce regroupant la commande d’éclairage, les modes automatique et naturel, la reprise et les scènes.
- La recherche par nom ou identifiant dans les sélecteurs d’entités et les listes de lampes, avec indication des groupes Home Assistant et des appartenances connues.
- L’allumage et l’extinction selon la présence et la luminosité, avec seuil, hystérésis et temporisations configurables.
- Une pause après une commande manuelle, avec une option par pièce pour maintenir les extinctions automatiques pendant cette pause.
- Des profils de lumière naturelle fondés sur l’élévation du soleil, associables à plusieurs groupes dans une même pièce, avec courbes de luminosité et de température de blanc adaptées aux lampes compatibles.
- Une ambiance de base et des scènes conditionnelles prioritaires, ordonnées dans le dashboard, avec édition en direct sur les lampes pendant la suspension de l’automatisation de la pièce.
- Des transitions par type de changement, définies globalement et personnalisables ou désactivables par pièce.
- L’anglais comme langue de référence, une traduction française suivant la langue de l’interface Home Assistant et un repli en anglais pour les autres langues. Les noms personnalisés restent inchangés.

Les pièces nouvellement configurées ont leurs automatismes **désactivés** jusqu’à leur activation. L’interface actuelle utilise une présentation fonctionnelle et les couleurs du thème Home Assistant ; la direction esthétique définitive reste à définir. Les étapes de validation figurent dans la [feuille de route](docs/ROADMAP.md).

Les nouveaux réglages proposent **0 seconde** de délai d’absence et **120 minutes** de pause manuelle. Les transitions globales initiales sont **0 s** à l’allumage, **10 s** après baisse de luminosité, **60 s** pour la lumière naturelle, **10 s** pour les scènes et **2 s** à l’extinction ; les pièces en héritent. Les valeurs déjà enregistrées sont conservées. Le seuil et l’hystérésis affichent l’unité du capteur (`lx`, `%`, etc.), sans conversion implicite. La création des profils et des scènes est compatible avec un accès local en HTTP.

Les transitions dépendent des capacités annoncées par chaque lampe. Sur les équipements qui ne restituent pas le contexte des commandes, la distinction entre une transition et une intervention physique repose sur les changements d’état observés et doit encore être vérifiée sur le matériel utilisé.

## Essai manuel en développement

La version de référence et le minimum déclaré sont **Home Assistant 2026.10.0**. La compatibilité avec les versions précédentes n’est pas revendiquée.

1. Copier le dossier `custom_components/halo` dans le dossier `custom_components` de la configuration d’une instance de test Home Assistant.
2. Redémarrer cette instance pour qu’elle découvre les fichiers.
3. Ouvrir **Paramètres → Appareils et services → Ajouter une intégration**.
4. Rechercher **Halo**, puis confirmer la configuration.

5. Ouvrir **Halo** dans la barre latérale, configurer une pièce, sélectionner ses lampes puis enregistrer. La configuration est réservée aux administrateurs.
6. Vérifier les commandes de la pièce, renseigner les capteurs et profils souhaités, puis activer les automatismes lorsque les réglages sont prêts.

Le dossier à copier contient déjà le bundle du panneau ; aucune compilation ni carte supplémentaire n’est nécessaire dans Home Assistant. Après remplacement du bundle pendant le développement, recharger également la page du navigateur. Pour retirer Halo, supprimer son entrée dans **Appareils et services**, puis son dossier si nécessaire.

## Développement

Avec [uv](https://docs.astral.sh/uv/) installé :

```sh
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
```

Pour modifier le panneau, utiliser Node.js 24 et npm :

```sh
npm ci
npm run check
npm test
npm run build
```

Le bundle généré doit accompagner toute modification des sources TypeScript. Le [guide du panneau](frontend/README.md) fournit un aperçu local avec des données simulées.

Le fichier `.python-version` fixe Python 3.14.5 ; `uv.lock` fixe les dépendances des tests. Aucune dépendance Python externe n’est requise par Halo dans l’instance Home Assistant.

Ce README, `PROJET.md` et `DESIGN.md` sont maintenus à jour en temps réel. Toute évolution doit être répercutée dans les documents concernés au cours de la même tâche, selon les consignes d’`AGENTS.md`.

- [Consignes pour les agents](AGENTS.md)
- [Projet et fonctionnalités](PROJET.md)
- [Design du dashboard](DESIGN.md)
- [Conventions de développement](docs/DEVELOPMENT.md)
- [Architecture et API du panneau](docs/ARCHITECTURE.md)
- [Documentation HACS étudiée et publication future](docs/HACS.md)
- [Feuille de route](docs/ROADMAP.md)
- [Icône et source graphique](assets/branding/README.md)

## Licence

[MIT](LICENSE).
