# Releases GitHub et distribution HACS

Documentation officielle reconsultée le **10 octobre 2026**. Les releases GitHub sont mises en place depuis le 9 octobre pour les installations comme dépôt personnalisé HACS. Le **10 octobre, Arnaud demande explicitement la soumission au catalogue HACS par défaut**, en remplacement du report à la fin du projet. L’examen et la fusion dépendent des mainteneurs HACS ; la disponibilité effective doit ensuite être vérifiée dans leur catalogue.

## Structure distribuée

HACS distribue une intégration personnalisée Home Assistant. Un seul domaine, `halo`, est présent dans `custom_components/`. Tout le contenu à installer, y compris le panneau compilé et le lotus, se trouve dans ce dossier. Le manifeste contient les coordonnées du dépôt existant `Gnol86/Halo`, le responsable et la version de l’intégration. [Exigences des intégrations](https://www.hacs.xyz/docs/publish/integration/).

Le fichier racine `hacs.json` indique le nom et le minimum Home Assistant. Les valeurs par défaut conviennent : pas d’archive ZIP à produire, pas de contenu à la racine et aucune restriction géographique. HACS demande aussi un dépôt public sur GitHub, une description, des sujets et un README d’utilisation. [Exigences générales](https://www.hacs.xyz/docs/publish/start/).

Depuis Home Assistant 2026.3, une intégration personnalisée peut embarquer ses images dans `brand/`. Halo utilise `brand/icon.png` et `brand/icon@2x.png` pour l’interface native Home Assistant, une fois les fichiers installés et l’intégration découverte. Cette prise en charge ne garantit pas l’affichage dans HACS. [Images de marque](https://developers.home-assistant.io/docs/core/integration/brand_images/).

## Versions et releases

Lorsqu’un dépôt publie des releases GitHub, HACS utilise le nom de tag de la dernière release comme version distante. **Créer ou pousser un tag seul ne suffit pas** : la release doit être publiée. HACS peut alors présenter les dernières releases au téléchargement et à la mise à jour. [Règles de versions](https://www.hacs.xyz/docs/publish/start/#versions) · [Releases d’intégrations](https://www.hacs.xyz/docs/publish/integration/#github-releases-optional).

Halo conserve le format standard : HACS lit `custom_components/halo/` au tag choisi. Aucun `zip_release`, `filename` ni ZIP spécifique n’est ajouté. Les archives sources générées automatiquement par GitHub ne constituent pas un paquet Halo distinct.

La première **[release `v0.1.0`](https://github.com/Gnol86/Halo/releases/tag/v0.1.0)** est publiée le **9 octobre 2026**, sans statut de brouillon ni de préversion. Le [workflow Release](https://github.com/Gnol86/Halo/actions/runs/37958464981) a réussi ses six jobs, dont HACS et Hassfest. L’archive GitHub du tag a été contrôlée : manifeste `0.1.0`, panneau compilé, images, traductions et licence concordent avec les fichiers locaux de cette version. Les preuves détaillées figurent dans [DEVELOPMENT.md](DEVELOPMENT.md). Le minimum Home Assistant reste `2026.10.0` ; l’installation réelle via HACS et la validation matérielle ne sont pas attestées par cette publication.

La **[release `v0.1.1`](https://github.com/Gnol86/Halo/releases/tag/v0.1.1)** est publiée le même jour et confirmée comme dernière release normale par GitHub. Elle regroupe les corrections de sélecteurs, d’alignement et de notification du panneau. Ses [six jobs de publication](https://github.com/Gnol86/Halo/actions/runs/37961233161) ont réussi, y compris HACS et Hassfest ; les 25 fichiers distribuables de l’archive ont été comparés au dépôt. Cette publication n’installe pas la mise à jour dans le logement.

La **[release v0.2.0](https://github.com/Gnol86/Halo/releases/tag/v0.2.0)** est publiée le **10 octobre 2026** et confirmée comme dernière release normale. Elle ajoute les scènes liées, les veilleuses et les autorisations sans capteur. Les [six jobs du workflow](https://github.com/Gnol86/Halo/actions/runs/38011179346) réussissent, y compris HACS sans contrôle ignoré et Hassfest. Les 28 fichiers de `custom_components/halo/` de l’archive GitHub sont identiques au tag `v0.2.0`, sur le commit `fbed7fc88685fc7baf0ad812c4be41bbdbe2a65d`. [Notes de version](../releases/0.2.0.md). Aucune installation domestique ne découle de cette publication.

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

## Référencement au catalogue

### Audit du 10 octobre 2026

Les exigences viennent des [règles générales](https://www.hacs.xyz/docs/publish/start/), des [règles des intégrations](https://www.hacs.xyz/docs/publish/integration/) et de la [procédure d’inclusion](https://www.hacs.xyz/docs/publish/include/). Le [modèle de PR](https://github.com/hacs/default/blob/master/.github/PULL_REQUEST_TEMPLATE.md) et les [contrôles du catalogue](https://github.com/hacs/default/tree/master/.github/workflows) ont aussi été relus.

| Condition | Preuve ou état Halo |
| --- | --- |
| Dépôt GitHub public, actif | API GitHub : `Gnol86/Halo`, public et non archivé. |
| Description, sujets, suivi des tickets activé | Description `Whole-home lighting management for Home Assistant.`, cinq sujets dont `hacs` et `home-assistant`, issues activées. |
| Licence reconnue par la validation HACS | Licence MIT présente à la racine et identifiée par l’API GitHub. |
| README expliquant l’utilisation | Présentation anglaise à la racine et traduction `docs/README.fr.md` : installation, premiers réglages et limites. |
| Manifeste HACS à la racine | `hacs.json` : nom `Halo`, minimum Home Assistant `2026.10.0`. Aucune restriction géographique. |
| Une seule intégration, distribuable complet | Domaine unique `custom_components/halo/`, panneau compilé, traductions et images inclus ; fichiers identiques à v0.2.0. |
| Manifeste de l’intégration complet | `domain`, `name`, `version`, `documentation`, `issue_tracker` et `codeowners` présents ; version `0.2.0`, propriétaire `@Gnol86`. |
| Image de marque embarquée | `brand/icon.png` 256 × 256 et `icon@2x.png` 512 × 512, PNG RGBA vérifiés. |
| Aucun remplacement d’une intégration du cœur | Domaine propre `halo` ; aucun dossier correspondant dans le registre des composants du cœur consulté via GitHub. Halo ne sert pas de variante alpha/bêta d’une intégration du cœur. |
| Compatibilité avec un dépôt personnalisé | Action officielle HACS réussie sur v0.2.0 ; cette action utilise les validations de HACS. L’installation et la mise à jour domestiques ne sont pas déduites de ce contrôle. |
| Actions HACS et Hassfest sans contrôle désactivé | [HACS](https://github.com/Gnol86/Halo/actions/runs/38011179346/job/114091326735) et [Hassfest](https://github.com/Gnol86/Halo/actions/runs/38011179346/job/114091326791) réussis avant publication ; aucun champ `ignore` dans le workflow HACS. |
| Release complète après les validations | [v0.2.0](https://github.com/Gnol86/Halo/releases/tag/v0.2.0), publiée le 10 octobre à 00:57:45 UTC après la fin des deux contrôles ; ni brouillon ni préversion. |
| Soumission par le propriétaire ou un contributeur majeur | Compte GitHub authentifié `Gnol86`, propriétaire du dépôt avec droits administrateur. |
| Absence de doublon ou retrait antérieur | `Gnol86/Halo` absent de `integration`, `blacklist` et `removed` ; aucune PR correspondante trouvée lors de la préparation. |
| PR modifiable, depuis une branche personnelle | [PR #11771](https://github.com/hacs/default/pull/11771) : `Gnol86/default:codex/add-halo` vers `hacs/default:master`, `maintainerCanModify=true`. Une seule ligne ajoutée dans `integration` ; JSON et tri officiel vérifiés localement. |
| Modèle et preuves complets | Modèle rempli dans la PR, avec les liens vers la release et les validations HACS/Hassfest antérieures à sa publication ; aucune demande explicite de revue. |

Les captures d’écran sont exigées pour les thèmes et plugins, pas pour une intégration. Une version minimale de Home Assistant et une restriction de pays doivent refléter la compatibilité réelle ; Halo n’impose aucun pays. La documentation ne fixe pas de seuil de popularité pour soumettre une intégration.

Le [nouveau contrôle officiel HACS](https://github.com/Gnol86/Halo/actions/runs/38048474644) réussit le 10 octobre 2026 : **9 vérifications sur 9**, sans exclusion, version distante détectée `v0.2.0`. Les fichiers distribuables n’ont pas changé depuis cette release ; aucune nouvelle version applicative n’est nécessaire pour cet ajout au catalogue.

### État de la démarche

La [PR #11771 — Add Gnol86/Halo](https://github.com/hacs/default/pull/11771) est ouverte le **10 octobre 2026**, sans statut de brouillon, par `Gnol86`. Le label **New default repository** est présent. Elle reprend le modèle officiel et les preuves des contrôles réussis avant la publication de v0.2.0. Aucun relecteur n’a été sollicité explicitement.

- [x] Vérifier les exigences officielles, les métadonnées GitHub et les preuves de la release 0.2.0.
- [x] Préparer les README anglais/français et actualiser la décision de soumission dans la documentation.
- [x] Publier la documentation : commit `631add2` sur `main` ; [validation GitHub](https://github.com/Gnol86/Halo/actions/runs/38048597507) réussie, avec tests Python, panneau et Hassfest.
- [x] Ouvrir la PR d’ajout dans `hacs/default` avec le modèle rempli et les preuves.
- [x] Vérifier tous les contrôles de la PR du catalogue : **12 sur 12 réussis**, workflows [Check](https://github.com/hacs/default/actions/runs/38048667096) et [Lint](https://github.com/hacs/default/actions/runs/38048664631).
- [ ] Obtenir la fusion par les mainteneurs.
- [ ] Confirmer la présence dans le catalogue distribué après le scan HACS.

HACS annonce que l’examen des nouvelles demandes peut prendre plusieurs mois. Une PR ouverte ou des contrôles réussis ne constituent donc pas une inclusion. Les validations matérielles de la [feuille de route](ROADMAP.md) restent à réaliser ; la demande de référencement ne les transforme pas en essais effectués.

À l’issue des contrôles, GitHub indique **OPEN**, **REVIEW_REQUIRED** et **BLOCKED** : l’approbation des mainteneurs manque encore. Le contrôle officiel **Existing repository** confirme l’absence de doublon dans les catalogues distribués au moment de la soumission. La vérification directe du catalogue depuis ce poste a reçu HTTP 403 ; elle n’est pas utilisée comme preuve de présence ou d’absence.

## Validation et limites

`.github/workflows/validate.yml` exécute les tests et Hassfest ; le workflow de release le réutilise avant publication. `.github/workflows/hacs.yml` fournit le contrôle HACS réutilisable et manuel, sans `ignore` et sans publication propre. Ses résultats bloquent également une release. Les métadonnées du dépôt doivent aussi satisfaire les exigences HACS. [Action officielle HACS](https://www.hacs.xyz/docs/publish/action/).

Publier une release, installer une intégration comme dépôt personnalisé et obtenir le référencement par défaut sont trois opérations distinctes. Le simple ajout de `hacs.json` ne réalise aucune d’elles. Les tests de code et d’interface avec lampes simulées ne remplacent pas les essais matériels prévus dans la feuille de route.
