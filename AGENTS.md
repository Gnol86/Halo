# Consignes pour les agents — Halo

## Communication

- Toujours parler français à Arnaud et le tutoyer.
- Distinguer ce qui est décidé, proposé, implémenté et vérifié.
- Signaler les limites des vérifications sans présenter une intention comme une fonctionnalité disponible.

## Contexte du projet

Halo est une intégration personnalisée Home Assistant destinée à gérer toutes les lumières du logement. Son domaine est `halo` et son symbole est une fleur de lotus.

Le projet contient une première implémentation du moteur d’éclairage, des entités par pièce et du panneau embarqué TypeScript/Lit, en plus du socle d’installation unique et des traductions. Des tests locaux couvrent le moteur, les plateformes, la persistance, l’API et le panneau. Les essais sur une instance domestique et les lampes réelles restent à faire. Relire l’état courant du code et des documents avant toute intervention.

Le cahier des charges fonctionnel est acté dans `PROJET.md` : panneau unique, appareils par pièce, présence et luminosité, pause manuelle, profils naturels, scènes et transitions. Les règles d’interface actées se trouvent dans `DESIGN.md`. La refonte compacte du 9 octobre 2026 est implémentée : pilotage prioritaire, liste/détail des pièces, cinq onglets par pièce, profils dans une vue dédiée et thème Home Assistant sans palette indépendante. Ces choix remplacent l’ancienne direction esthétique laissée ouverte. Les contrats de code sont décrits dans [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

Préserver tous les réglages métier dans les sous-vues, le brouillon transversal, la validation avant navigation et les garanties de l’édition réelle. La fenêtre native d’une lampe utilise l’action publique Home Assistant ; les sélecteurs d’entités restent ceux de Halo, faute de contrat public de chargement identifié pour ce panneau. Ne pas présenter leur remplacement natif comme implémenté. Les essais ciblés dans Home Assistant isolé utilisent des lampes simulées et ne prouvent pas le comportement du matériel du logement.

L’anglais est la langue de référence du produit. Le panneau doit suivre la langue effective de l’interface Home Assistant : français pour `fr` et ses variantes, anglais autrement, avec des catalogues extensibles. Préserver les noms personnalisés et les identifiants techniques. Cette règle produit ne change pas la communication avec Arnaud, qui reste en français.

La distribution via HACS est prévue **à la fin du projet**. Le référencement n’est pas une tâche à lancer pendant la préparation du socle ou la définition des fonctionnalités. La procédure future se trouve dans [docs/HACS.md](docs/HACS.md).

## Documents à lire

Avant de travailler sur le projet, lire :

1. [PROJET.md](PROJET.md) : référence des objectifs, fonctionnalités, comportements et décisions produit.
2. [DESIGN.md](DESIGN.md) : référence des règles de design et d’interaction du dashboard.
3. [README.md](README.md) : état présenté aux utilisateurs et installation.

Selon la tâche, consulter également [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md), [docs/ROADMAP.md](docs/ROADMAP.md) et [docs/HACS.md](docs/HACS.md). La feuille de route organise les jalons ; les spécifications détaillées appartiennent à `PROJET.md` et `DESIGN.md`.

Pour une évolution de l’interface, consulter aussi [PRODUCT.md](PRODUCT.md) et le [contrat de direction du panneau](.impeccable/surfaces/frontend-src-halo-panel-ts.md). Ils résument le contexte de conception ; ils ne remplacent pas les spécifications fonctionnelles et les règles de `DESIGN.md`.

## Mise à jour en temps réel — obligatoire

**`PROJET.md`, `DESIGN.md` et `README.md` doivent être tenus à jour en temps réel, au fil des échanges et du travail.** Ne pas attendre la fin d’un jalon, une release ou une demande de documentation séparée.

- Dès qu’une fonctionnalité, un comportement, une priorité ou une décision produit est ajouté, précisé, modifié ou abandonné, mettre à jour `PROJET.md` dans la même tâche.
- Dès qu’une règle visuelle, une interaction ou une décision concernant le dashboard évolue, mettre à jour `DESIGN.md` dans la même tâche.
- Dès qu’une évolution change les fonctionnalités disponibles, l’installation, la configuration, la compatibilité, les limites ou le statut de distribution, mettre à jour `README.md` dans la même tâche. Il doit décrire fidèlement ce qu’un utilisateur peut réellement utiliser ; identifier explicitement les fonctions seulement prévues.
- Quand une décision concerne plusieurs de ces documents, les mettre à jour ensemble et vérifier leur cohérence.
- Une proposition ou une question ouverte doit rester explicitement marquée comme telle. Ne pas transformer une idée en décision validée ni inventer des règles pour remplir une rubrique.
- Lors de l’implémentation, actualiser le statut et les preuves de validation des éléments concernés. « Implémenté » ne signifie pas « testé dans une instance Home Assistant ».
- Préserver les notes et décisions manuelles existantes. Si une décision est remplacée, indiquer ce qui change et conserver le contexte utile.
- Actualiser la date de mise à jour des documents modifiés lorsqu’ils en affichent une. Avant de terminer une tâche, relire `PROJET.md`, `DESIGN.md` et `README.md` pour vérifier qu’ils reflètent les décisions prises et le comportement effectivement livré.

Ces mises à jour font partie du travail demandé ; elles ne nécessitent pas une confirmation supplémentaire. Mettre aussi à jour la feuille de route ou les présentes consignes lorsque leur contenu devient obsolète.

## Repères techniques

- Code et ressources distribuables : `custom_components/halo/`.
- Métadonnées Home Assistant : `custom_components/halo/manifest.json` ; métadonnées HACS : `hacs.json`.
- Tests : `tests/` ; environnement de développement : `pyproject.toml`, `.python-version` et `uv.lock`.
- Icônes embarquées : `custom_components/halo/brand/` ; source et prompt : `assets/branding/`.
- Sources du panneau : `frontend/src/` ; bundle à reconstruire et distribuer : `custom_components/halo/frontend/halo-panel.js`.
- Workflows de validation : `.github/workflows/`. Leur présence ne prouve pas leur exécution ni une publication.

Inspecter l’état Git et préserver les changements existants. Pour une modification de code, exécuter les vérifications adaptées :

```sh
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
```

Pour le panneau (Node.js 24), exécuter `npm ci`, `npm run check`, `npm test` et `npm run build`. Conserver le bundle synchronisé avec les sources ; le workflow vérifie sa reproductibilité. Les aperçus avec données simulées ne doivent pas être présentés comme un essai dans Home Assistant.

Pour une modification uniquement documentaire, vérifier les liens, la cohérence et le contenu ; ne pas relancer les tests applicatifs sans raison. Les résultats historiques sont consignés dans `docs/DEVELOPMENT.md` et ne remplacent pas une validation des changements ultérieurs.
