# Feuille de route

Dernière mise à jour : **9 octobre 2026**.

Cette feuille de route suit les jalons. Les fonctionnalités et décisions produit sont détaillées dans [PROJET.md](../PROJET.md), et les règles du dashboard dans [DESIGN.md](../DESIGN.md). Ces deux documents sont mis à jour en temps réel.

Le cahier des charges fonctionnel est défini et documenté. Le pilotage des lumières et le dashboard restent **à développer** ; une case cochée dans le jalon de définition ne signifie pas qu’une fonction est implémentée ou validée dans Home Assistant.

## 1. Socle

- [x] Étudier les exigences Home Assistant et HACS.
- [x] Créer la structure `custom_components/halo` et les métadonnées.
- [x] Préparer une configuration unique depuis l’interface, en français et en anglais.
- [x] Créer le lotus et l’embarquer dans l’intégration.
- [x] Préparer les tests et les workflows de validation.

## 2. Définition du fonctionnement

- [x] Documenter le panneau unique, l’organisation par pièce, les appareils et les droits de configuration.
- [x] Définir la sélection explicite des lumières, leurs exclusions et l’affectation unique à une pièce et à un profil naturel.
- [x] Définir la présence, les seuils lumineux, l’hystérésis, les délais et la pause manuelle, avec politique d’extinction configurable par pièce.
- [x] Définir l’ambiance de base, les profils naturels multiples, les courbes solaires et l’adaptation aux capacités des lampes.
- [x] Définir les scènes, leurs conditions et priorités, ainsi que leur édition en direct.
- [x] Définir les cinq catégories de transitions, les valeurs globales et les choix par pièce.
- [x] Définir l’anglais de référence, le français, le suivi de la langue de l’interface et le repli anglais.
- [x] Documenter les choix d’architecture, les valeurs initiales, les limites des données indisponibles et les scénarios d’acceptation.
- [x] Consigner l’organisation et les interactions retenues dans `DESIGN.md`.
- [ ] Définir l’apparence détaillée du dashboard et ses règles visuelles, d’accessibilité, d’adaptation aux écrans et aux thèmes.

## 3. Première version fonctionnelle

- [ ] Construire le moteur Python par pièce, le stockage versionné et les commandes WebSocket authentifiées.
- [ ] Ajouter le panneau embarqué TypeScript/Lit, les pièces Home Assistant, la sélection des lumières et les entités des appareils Halo.
- [ ] Implémenter la présence, la luminosité, les pauses manuelles, la reprise et les transitions.
- [ ] Implémenter l’ambiance de base, les profils naturels, leurs associations et les adaptations aux capacités des lampes.
- [ ] Implémenter les scènes conditionnelles ordonnées, leur exposition dans Home Assistant et l’édition réelle avec restauration et expiration des sessions.
- [ ] Ajouter les textes anglais et français, la langue par utilisateur et les états explicatifs du dashboard.
- [ ] Couvrir les scénarios d’acceptation de `PROJET.md`, notamment les priorités, les indisponibilités, les accès concurrents et les droits côté serveur.
- [ ] Tester le redémarrage, les pauses persistées, le déchargement, la désactivation et les changements d’état externes, sans confondre les commandes Halo avec une intervention manuelle.
- [ ] Valider sur une instance Home Assistant de test avec des lampes marche/arrêt, dimmables, à température de blanc et à couleur, y compris les transitions prises en charge ou absentes.
- [ ] Vérifier l’installation, le panneau, les langues et les interactions sur les écrans et thèmes retenus ; consigner les résultats et leurs limites.
- [ ] Actualiser les statuts dans `PROJET.md` et `DESIGN.md`, et présenter uniquement les fonctions réellement livrées comme disponibles dans le [README](../README.md).

## 4. Publication, en dernier

- [ ] Suivre la [liste de publication HACS](HACS.md).
- [ ] Publier une première release utilisable.
- [ ] Demander ensuite l’inclusion au catalogue HACS par défaut.
