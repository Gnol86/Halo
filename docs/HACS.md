# Releases GitHub et distribution HACS

Documentation officielle reconsultée le **10 octobre 2026**. À la demande d’Arnaud, les **releases GitHub sont mises en place maintenant** pour les installations comme dépôt personnalisé HACS. Le **référencement au catalogue par défaut reste un jalon final**. Cette précision remplace le report initial de toute publication ; elle n’autorise aucune soumission automatique à `hacs/default`.

## Structure distribuée

HACS distribue une intégration personnalisée Home Assistant. Un seul domaine, `halo`, est présent dans `custom_components/`. Tout le contenu à installer, y compris le panneau compilé et le lotus, se trouve dans ce dossier. Le manifeste contient les coordonnées du dépôt existant `Gnol86/Halo`, le responsable et la version de l’intégration. [Exigences des intégrations](https://www.hacs.xyz/docs/publish/integration/).

Le fichier racine `hacs.json` indique le nom et le minimum Home Assistant. Les valeurs par défaut conviennent : pas d’archive ZIP à produire, pas de contenu à la racine et aucune restriction géographique. HACS demande aussi un dépôt public sur GitHub, une description, des sujets et un README d’utilisation. [Exigences générales](https://www.hacs.xyz/docs/publish/start/).

Depuis Home Assistant 2026.3, une intégration personnalisée peut embarquer ses images dans `brand/`. Halo utilise `brand/icon.png` et `brand/icon@2x.png` pour l’interface native Home Assistant, une fois les fichiers installés et l’intégration découverte. Cette prise en charge ne garantit pas l’affichage dans HACS. [Images de marque](https://developers.home-assistant.io/docs/core/integration/brand_images/).

## Versions et releases

Lorsqu’un dépôt publie des releases GitHub, HACS utilise le nom de tag de la dernière release comme version distante. **Créer ou pousser un tag seul ne suffit pas** : la release doit être publiée. HACS peut alors présenter les dernières releases au téléchargement et à la mise à jour. [Règles de versions](https://www.hacs.xyz/docs/publish/start/#versions) · [Releases d’intégrations](https://www.hacs.xyz/docs/publish/integration/#github-releases-optional).

Halo conserve le format standard : HACS lit `custom_components/halo/` au tag choisi. Aucun `zip_release`, `filename` ni ZIP spécifique n’est ajouté. Les archives sources générées automatiquement par GitHub ne constituent pas un paquet Halo distinct.

La première **[release `v0.1.0`](https://github.com/Gnol86/Halo/releases/tag/v0.1.0)** est publiée le **9 octobre 2026**, sans statut de brouillon ni de préversion. Le [workflow Release](https://github.com/Gnol86/Halo/actions/runs/37958464981) a réussi ses six jobs, dont HACS et Hassfest. L’archive GitHub du tag a été contrôlée : manifeste `0.1.0`, panneau compilé, images, traductions et licence concordent avec les fichiers locaux de cette version. Les preuves détaillées figurent dans [DEVELOPMENT.md](DEVELOPMENT.md). Le minimum Home Assistant reste `2026.10.0` ; l’installation réelle via HACS et la validation matérielle ne sont pas attestées par cette publication.

La **[release `v0.1.1`](https://github.com/Gnol86/Halo/releases/tag/v0.1.1)** est publiée le même jour et confirmée comme dernière release normale par GitHub. Elle regroupe les corrections de sélecteurs, d’alignement et de notification du panneau. Ses [six jobs de publication](https://github.com/Gnol86/Halo/actions/runs/37961233161) ont réussi, y compris HACS et Hassfest ; les 25 fichiers distribuables de l’archive ont été comparés au dépôt. Cette publication n’installe pas la mise à jour dans le logement.

La version **0.2.0** est préparée le **10 octobre 2026** avec les scènes liées, les veilleuses et les autorisations sans capteur. Versions et notes sont synchronisées ; la publication reste conditionnée à la réussite du workflow. [Notes de version](../releases/0.2.0.md).

### Contrat du workflow

Le workflow `.github/workflows/release.yml` est déclenché par le push d’un tag `v*`, ou relancé manuellement sur un tag existant. Un push de développement sur `main` ne crée pas de release.

- Le tag doit être de la forme `vX.Y.Z`, ou `vX.Y.ZaN`, `vX.Y.ZbN`, `vX.Y.ZrcN` pour une préversion, par exemple `v0.2.0b1`.
- La version sans le `v` doit correspondre exactement à `custom_components/halo/manifest.json` et à `pyproject.toml` ; le verrou `uv.lock` reste synchronisé.
- Le fichier `releases/<version>.md` est obligatoire et fournit les notes rédigées : changements, compatibilité, installation et limites.
- `scripts/release_metadata.py` contrôle ces métadonnées, y compris la version dans `uv.lock`. Le workflow réutilise les vérifications Python, frontend, reproductibilité du bundle et Hassfest de `validate.yml`, ainsi que **HACS readiness** sans contrôle ignoré, avant de créer la release.
- La publication utilise le tag déjà présent et les notes rédigées, complétées par le journal généré par GitHub. Les suffixes `a`, `b` et `rc` créent une **préversion**, jamais désignée comme dernière release normale.

Ce workflow ne soumet pas le dépôt au catalogue et ne redémarre aucune instance Home Assistant.

### Préparer une prochaine version

1. Mettre à jour le manifeste et `pyproject.toml` avec la même version, puis synchroniser `uv.lock`.
2. Ajouter `releases/<version>.md`, actualiser les documents concernés et exécuter les contrôles de développement. Le bundle compilé doit accompagner ses sources.
3. Enregistrer et pousser les changements sur `main`, puis créer et pousser un tag annoté `v<version>` sur le commit retenu. Ne pas déplacer un tag déjà publié.
4. Vérifier la réussite du workflow **Release**, puis ouvrir la release GitHub et contrôler son tag, ses notes et son statut de préversion éventuel. Un workflow en cours ou en échec ne vaut pas publication.
5. Vérifier séparément la détection et l’installation de la version dans HACS. Le workflow **HACS readiness** reste aussi exécutable manuellement pour recontrôler le dépôt. Les résultats sur GitHub ne prouvent pas l’installation ni l’activation dans le logement.

L’action HACS contrôle le dépôt avec les règles HACS ; le contrôle est bloquant avant publication et disponible manuellement. Le choix de la référence vérifiée dépend de l’événement : l’action distingue les pushes, les demandes de fusion et les dépôts utilisant déjà des releases. [Action officielle HACS](https://www.hacs.xyz/docs/publish/action/).

## Affichage du lotus

### Barre latérale Home Assistant

L’entrée **Halo** de la barre latérale relève de `panel_custom` de Home Assistant. Son icône se définit par `sidebar_icon`, indépendamment des images de la liste HACS. Halo utilise **`mdi:spa`**, une fleur de lotus native et monochrome, dans la barre latérale et l’en-tête du panneau. `flower-lotus` est un mot-clé du catalogue, pas un identifiant d’icône à préfixer par `mdi:`. La couleur est gérée par Home Assistant selon le thème et la sélection. [Panneaux personnalisés](https://developers.home-assistant.io/docs/frontend/custom-ui/creating-custom-panels/) · [Icône officielle `spa`](https://pictogrammers.com/library/mdi/icon/spa/).

### Liste et présentation HACS

Diagnostic du **9 octobre 2026**, sur HACS **2.0.5**, interface **20250128065759**, avec Halo ajouté comme dépôt personnalisé mais pas encore téléchargé :

- **Page de présentation :** le README utilisait une balise HTML avec un chemin d’image relatif, donnant une image cassée dans HACS. Le chemin est remplacé par l’URL absolue de `icon@2x.png` sur `raw.githubusercontent.com`. Cette URL répond en HTTP 200 avec un PNG identique au fichier local. Le changement doit être poussé sur GitHub puis repris par HACS pour être visible dans cette page ; le rendu corrigé dans HACS n’a pas encore été vérifié.
- **Liste des dépôts :** cette version de HACS demande encore l’image au CDN `brands.home-assistant.io`, sans lire le dossier `brand/` de Halo. Le dossier local est conforme au mécanisme Home Assistant. Ajouter un champ `icon` à `hacs.json` ne corrigerait pas le problème : ce champ n’est pas pris en charge. [Champs de `hacs.json`](https://www.hacs.xyz/docs/publish/start/#hacsjson).

La correction proposée dans [hacs/integration #5388](https://github.com/hacs/integration/pull/5388) et [hacs/frontend #945](https://github.com/hacs/frontend/pull/945) vise à servir les images locales des intégrations téléchargées et à récupérer celles des autres dépôts sur GitHub. Ces deux propositions sont encore ouvertes à la date du diagnostic ; il faudra vérifier une version HACS qui les intègre avant d’annoncer cette limite résolue. Une installation de Halo ne corrige pas à elle seule la liste de HACS 2.0.5.

Le dépôt `home-assistant/brands` n’accepte plus les images des nouvelles intégrations personnalisées : les images doivent rester embarquées dans Halo. Aucune soumission à ce dépôt ni au catalogue HACS n’est effectuée pour ce correctif. [Annonce officielle du changement](https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/).

## Référencement au catalogue, en dernier

- [ ] Terminer et vérifier les fonctions d’éclairage sur une instance de test.
- [ ] Actualiser le README avec les fonctions, limites et instructions réellement disponibles.
- [ ] Confirmer la compatibilité et ajuster le minimum Home Assistant si nécessaire.
- [ ] Recontrôler les exigences officielles HACS au moment de publier.
- [x] Compléter la description GitHub : `Whole-home lighting management for Home Assistant.`
- [x] Ajouter les sujets GitHub : `home-assistant`, `hacs`, `custom-integration`, `lighting`, `halo` ; conserver les issues activées.
- [ ] Vérifier l’installation et la mise à jour comme dépôt personnalisé HACS.
- [x] Obtenir des résultats verts pour Hassfest et l’action HACS, **sans contrôle ignoré** : workflow Release de `v0.1.0` réussi le 9 octobre 2026.
- [x] Confirmer qu’une release GitHub est publiée, avec une version cohérente dans le manifeste : `v0.1.0`, archive vérifiée ; l’installation et la mise à jour HACS restent à valider séparément.
- [ ] Depuis une branche d’un fork personnel de `hacs/default`, proposer `Gnol86/Halo` dans la liste `integration`, à sa place alphabétique, en remplissant le modèle de PR.
- [ ] Attendre l’examen et la fusion par les mainteneurs, puis vérifier l’apparition effective dans le catalogue.

Le propriétaire ou un contributeur majeur doit soumettre la demande. L’inclusion dépend des mainteneurs HACS et n’est jamais automatique. [Procédure officielle d’inclusion](https://www.hacs.xyz/docs/publish/include/).

## Validation et limites

`.github/workflows/validate.yml` exécute les tests et Hassfest ; le workflow de release le réutilise avant publication. `.github/workflows/hacs.yml` fournit le contrôle HACS réutilisable et manuel, sans `ignore` et sans publication propre. Ses résultats bloquent également une release. Les métadonnées du dépôt doivent aussi satisfaire les exigences HACS. [Action officielle HACS](https://www.hacs.xyz/docs/publish/action/).

Publier une release, installer une intégration comme dépôt personnalisé et obtenir le référencement par défaut sont trois opérations distinctes. Le simple ajout de `hacs.json` ne réalise aucune d’elles. Les tests de code et d’interface avec lampes simulées ne remplacent pas les essais matériels prévus dans la feuille de route.
