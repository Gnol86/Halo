# Préparer la distribution HACS

Documentation officielle consultée le **9 octobre 2026**. **La publication est un jalon final, pas une action de cette initialisation.**

## Structure préparée

HACS distribue une intégration personnalisée Home Assistant. Un seul domaine, `halo`, est présent dans `custom_components/`. Tout le contenu à installer, y compris le lotus, se trouve dans ce dossier. Le manifeste contient les coordonnées du dépôt existant `Gnol86/Halo`, le responsable et une version de développement. [Exigences des intégrations](https://www.hacs.xyz/docs/publish/integration/).

Le fichier racine `hacs.json` indique le nom et le minimum Home Assistant. Les valeurs par défaut conviennent : pas d’archive ZIP à produire, pas de contenu à la racine et aucune restriction géographique. HACS demande aussi un dépôt public sur GitHub, une description, des sujets et un README d’utilisation. [Exigences générales](https://www.hacs.xyz/docs/publish/start/).

Depuis Home Assistant 2026.3, une intégration personnalisée peut embarquer ses images dans `brand/`. Halo utilise `brand/icon.png` et `brand/icon@2x.png` pour l’interface native Home Assistant, une fois les fichiers installés et l’intégration découverte. Cette prise en charge ne garantit pas l’affichage dans HACS. [Images de marque](https://developers.home-assistant.io/docs/core/integration/brand_images/).

## Affichage du lotus

Diagnostic du **9 octobre 2026**, sur HACS **2.0.5**, interface **20250128065759**, avec Halo ajouté comme dépôt personnalisé mais pas encore téléchargé :

- **Page de présentation :** le README utilisait une balise HTML avec un chemin d’image relatif, donnant une image cassée dans HACS. Le chemin est remplacé par l’URL absolue de `icon@2x.png` sur `raw.githubusercontent.com`. Cette URL répond en HTTP 200 avec un PNG identique au fichier local. Le changement doit être poussé sur GitHub puis repris par HACS pour être visible dans cette page ; le rendu corrigé dans HACS n’a pas encore été vérifié.
- **Liste des dépôts :** cette version de HACS demande encore l’image au CDN `brands.home-assistant.io`, sans lire le dossier `brand/` de Halo. Le dossier local est conforme au mécanisme Home Assistant. Ajouter un champ `icon` à `hacs.json` ne corrigerait pas le problème : ce champ n’est pas pris en charge. [Champs de `hacs.json`](https://www.hacs.xyz/docs/publish/start/#hacsjson).

La correction proposée dans [hacs/integration #5388](https://github.com/hacs/integration/pull/5388) et [hacs/frontend #945](https://github.com/hacs/frontend/pull/945) vise à servir les images locales des intégrations téléchargées et à récupérer celles des autres dépôts sur GitHub. Ces deux propositions sont encore ouvertes à la date du diagnostic ; il faudra vérifier une version HACS qui les intègre avant d’annoncer cette limite résolue. Une installation de Halo ne corrige pas à elle seule la liste de HACS 2.0.5.

Le dépôt `home-assistant/brands` n’accepte plus les images des nouvelles intégrations personnalisées : les images doivent rester embarquées dans Halo. Aucune soumission à ce dépôt ni au catalogue HACS n’est effectuée pour ce correctif. [Annonce officielle du changement](https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/).

## À exécuter à la fin du projet

- [ ] Terminer et vérifier les fonctions d’éclairage sur une instance de test.
- [ ] Actualiser le README avec les fonctions, limites et instructions réellement disponibles.
- [ ] Confirmer la compatibilité et ajuster le minimum Home Assistant si nécessaire.
- [ ] Recontrôler les exigences officielles HACS au moment de publier.
- [ ] Compléter la description GitHub : `Whole-home lighting management for Home Assistant.`
- [ ] Ajouter les sujets GitHub : `home-assistant`, `hacs`, `custom-integration`, `lighting`, `halo` ; conserver les issues activées.
- [ ] Vérifier l’installation et la mise à jour comme dépôt personnalisé HACS.
- [ ] Obtenir des résultats verts pour Hassfest et l’action HACS, **sans contrôle ignoré**.
- [ ] Publier une vraie GitHub Release avec une version cohérente dans le manifeste ; un tag seul ne suffit pas.
- [ ] Depuis une branche d’un fork personnel de `hacs/default`, proposer `Gnol86/Halo` dans la liste `integration`, à sa place alphabétique, en remplissant le modèle de PR.
- [ ] Attendre l’examen et la fusion par les mainteneurs, puis vérifier l’apparition effective dans le catalogue.

Le propriétaire ou un contributeur majeur doit soumettre la demande. L’inclusion dépend des mainteneurs HACS et n’est jamais automatique. [Procédure officielle d’inclusion](https://www.hacs.xyz/docs/publish/include/).

## Validation préparée

`.github/workflows/validate.yml` prépare les tests et Hassfest. `.github/workflows/hacs.yml` prépare un contrôle HACS manuel, sans `ignore` et sans publication. Il faudra compléter les métadonnées du dépôt avant son exécution finale. [Action officielle HACS](https://www.hacs.xyz/docs/publish/action/).

Installer HACS, installer une intégration comme dépôt personnalisé et obtenir le référencement par défaut sont trois opérations distinctes. Le simple ajout de `hacs.json` ne réalise aucune d’elles.
