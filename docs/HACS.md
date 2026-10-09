# Préparer la distribution HACS

Documentation officielle consultée le **9 octobre 2026**. **La publication est un jalon final, pas une action de cette initialisation.**

## Structure préparée

HACS distribue une intégration personnalisée Home Assistant. Un seul domaine, `halo`, est présent dans `custom_components/`. Tout le contenu à installer, y compris le lotus, se trouve dans ce dossier. Le manifeste contient les coordonnées du dépôt existant `Gnol86/Halo`, le responsable et une version de développement. [Exigences des intégrations](https://www.hacs.xyz/docs/publish/integration/).

Le fichier racine `hacs.json` indique le nom et le minimum Home Assistant. Les valeurs par défaut conviennent : pas d’archive ZIP à produire, pas de contenu à la racine et aucune restriction géographique. HACS demande aussi un dépôt public sur GitHub, une description, des sujets et un README d’utilisation. [Exigences générales](https://www.hacs.xyz/docs/publish/start/).

Depuis Home Assistant 2026.3, une intégration personnalisée peut embarquer ses images dans `brand/`. Halo utilise `brand/icon.png` et `brand/icon@2x.png` ; aucune contribution à `home-assistant/brands` n’est nécessaire pour cette approche. [Images de marque](https://developers.home-assistant.io/docs/core/integration/brand_images/).

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
