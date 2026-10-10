# Panneau Halo

Interface TypeScript et Lit embarquée dans l’intégration. Le bundle ne charge aucune bibliothèque depuis un CDN. La direction compacte retenue le 9 octobre 2026 privilégie le pilotage, une liste de pièces et leur détail, et les variables du thème Home Assistant sans palette propre.

La navigation globale sépare **Pièces**, **Profils de lumière naturelle** et **Réglages globaux**. Le détail d’une pièce propose **Pilotage**, **Lumières**, **Automatisation**, **Ambiances** et **Réglages** aux administrateurs ; les autres utilisateurs gardent le pilotage. La liste des pièces possède une recherche, des états et des commandes rapides. Elle reste visible à côté du détail sur ordinateur ; sur mobile, la liste et le détail sont affichés successivement avec un retour. Les profils sont édités un à un, les aides et réglages secondaires se déplient.

```sh
npm ci
npm run check
npm test
npm run build
```

Le build produit `custom_components/halo/frontend/halo-panel.js`, chargé par le panneau personnalisé `halo-panel`. Conserver ce fichier avec les sources distribuées de l’intégration et le reconstruire après toute modification du frontend. La licence des bibliothèques Lit embarquées est conservée dans `custom_components/halo/frontend/LICENSE-Lit.txt`, en complément des notices du bundle.

Les tests DOM utilisent une connexion Home Assistant simulée : ils couvrent les droits visibles, les langues, l’enregistrement avec révision, les conflits de modification, l’édition avec verrou et l’annulation. La refonte ajoute la navigation clavier des onglets, la conservation du brouillon entre sous-vues, le refus de navigation en cas de champ invalide, la révélation des erreurs, les retours de focus et le changement de mode clair/sombre. Ils ne remplacent pas les essais sur les lampes du logement.

Le brouillon reste transversal à la navigation. Les saisies valides sont synchronisées dès `input` ; une saisie numérique invalide reste visible et bloque la sortie de la sous-vue ou la sauvegarde. La validation ouvre les sections repliées et focalise le premier champ concerné. L’abandon reconstruit la vue pour supprimer également les saisies invalides non intégrées au modèle. La barre d’enregistrement occupe un espace permanent au bas du panneau lorsqu’un brouillon existe, sans recouvrir les derniers champs. L’édition réelle conserve sa propre barre d’actions et bloque les changements de destination.

`styles.ts` et `entity-picker.ts` utilisent les variables de Home Assistant pour les couleurs, états, polices, tailles, espacements, bordures, rayons, en-tête et champs, avec des valeurs de repli. `hass.themes.darkMode` synchronise `color-scheme` lorsqu’il est fourni ; sinon celui-ci reste hérité. Les icônes sont des `ha-icon` monochromes et la préférence de mouvement réduit supprime les animations et transitions visuelles.

Les sélecteurs partagent le composant `halo-entity-picker` : recherche sans casse ni accents par nom/identifiant, navigation clavier et sélection explicite. Les tests couvrent aussi les unités des capteurs, les informations de groupe et la création de profils/scènes avec `crypto.randomUUID` absent, comme sur une adresse HTTP locale. Le helper `createId` utilise `getRandomValues` sans imposer HTTPS au panneau.

`dev.html` fournit un environnement visuel avec données simulées, sans connexion à un logement réel. Après le build, servir la racine du dépôt avec un serveur HTTP local puis ouvrir `/frontend/dev.html`. La démonstration comprend plusieurs pièces, états et profils ; des boutons changent la langue, le rôle et le thème (clair, sombre, personnalisé), avec une police à 125 %. Les aperçus ont été vérifiés à 390 et 1 436 pixels de large. Les icônes SVG de ce simulateur servent uniquement à sa prévisualisation ; le panneau distribué utilise les icônes Home Assistant. Ce fichier ne fait pas partie des ressources distribuées de l’intégration.

L’anglais est le catalogue de référence dans `src/translations.ts`. Le français utilise les mêmes clés ; les tests vérifient leur parité. Les noms personnalisés ne sont pas traduits. La langue effective du frontend Home Assistant prend le pas sur une langue globale.

Les réglages passent par `halo/get`, `halo/subscribe` et `halo/save`. Les commandes explicites utilisent `halo/command`. L’édition en direct utilise `halo/edit/begin`, `halo/edit/preview`, `halo/edit/touch` et `halo/edit/end` ; le serveur reste responsable des droits, de la validation, du verrou et de son expiration. Une session est renouvelée toutes les 20 secondes tant que le panneau est connecté.

Dans l’éditeur de scène, un clic sur une ligne de lampe émet l’action publique `hass-action` avec `more-info`. Home Assistant ouvre sa propre fenêtre ; aucun import de composant interne n’est nécessaire. La scène existante est prévisualisée une fois avant de donner la main aux contrôles natifs. L’enregistrement transmet `capture: true` pour capturer les états réels côté serveur, effets compris, sans renvoyer un ancien aperçu. Le simulateur `dev.html` indique que cette fenêtre exige Home Assistant et ne prétend pas la reproduire.

Les sélecteurs d’entités restent le composant Halo : aucun contrat public garantissant le chargement du sélecteur natif dans ce panneau n’a été identifié. La refonte adapte leurs styles au thème mais n’ajoute aucun chargement indirect de Lovelace ni import de composant privé.

L’import lit la configuration d’une scène avec `hass.callApi`, puis utilise `halo/scene/import` pour la normalisation et le filtrage serveur. La confirmation ajoute seulement la copie au brouillon ; la sauvegarde passe par `halo/save`. Le parcours ne lance aucune scène. Dans l’éditeur, les cases d’inclusion sont conservées pour les scènes partielles et sont transmises comme `capture_entities` lors de l’enregistrement. Une réponse d’import reçue après annulation ou navigation ne modifie pas le brouillon.

Après la refonte, des parcours ciblés ont aussi été vérifiés dans Home Assistant 2026.10.0 isolé avec le frontend officiel et des lampes simulées : édition d’une scène partielle à deux lampes sur quatre, ouverture native avec effet « Candle », annulation libérant la session, puis import de deux lampes retenues/deux entités ignorées jusqu’au brouillon et à son abandon. Aucune erreur console n’a été relevée pendant ces parcours. Ce résultat local n’annonce ni push, ni déploiement domestique.
