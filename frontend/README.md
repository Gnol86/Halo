# Panneau Halo

Interface TypeScript et Lit embarquée dans l’intégration. Le bundle ne charge aucune bibliothèque depuis un CDN. Les styles suivent les variables de thème Home Assistant ; la direction esthétique définitive reste ouverte.

```sh
npm ci
npm run check
npm test
npm run build
```

Le build produit `custom_components/halo/frontend/halo-panel.js`, chargé par le panneau personnalisé `halo-panel`. Conserver ce fichier avec les sources distribuées de l’intégration et le reconstruire après toute modification du frontend. La licence des bibliothèques Lit embarquées est conservée dans `custom_components/halo/frontend/LICENSE-Lit.txt`, en complément des notices du bundle.

Les tests DOM utilisent une connexion Home Assistant simulée : ils couvrent les droits visibles, les langues, l’enregistrement avec révision, les conflits de modification, l’édition avec verrou et l’annulation. Ils ne remplacent pas un essai du panneau dans une instance Home Assistant ni une vérification visuelle sur mobile.

`dev.html` fournit un environnement visuel avec données simulées, sans connexion à un logement réel. Après le build, servir la racine du dépôt avec un serveur HTTP local puis ouvrir `/frontend/dev.html`. Des boutons permettent de changer de langue, de thème et de rôle. Ce fichier ne fait pas partie des ressources distribuées de l’intégration.

L’anglais est le catalogue de référence dans `src/translations.ts`. Le français utilise les mêmes clés ; les tests vérifient leur parité. Les noms personnalisés ne sont pas traduits. La langue effective du frontend Home Assistant prend le pas sur une langue globale.

Les réglages passent par `halo/get`, `halo/subscribe` et `halo/save`. Les commandes explicites utilisent `halo/command`. L’édition en direct utilise `halo/edit/begin`, `halo/edit/preview`, `halo/edit/touch` et `halo/edit/end` ; le serveur reste responsable des droits, de la validation, du verrou et de son expiration. Une session est renouvelée toutes les 20 secondes tant que le panneau est connecté.
