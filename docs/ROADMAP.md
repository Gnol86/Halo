# Feuille de route

Dernière mise à jour : **9 octobre 2026**.

Cette feuille de route suit les jalons. Les fonctionnalités et décisions produit sont détaillées dans [PROJET.md](../PROJET.md), et les règles du dashboard dans [DESIGN.md](../DESIGN.md). Ces deux documents sont mis à jour en temps réel.

Le cahier des charges fonctionnel est défini et une première implémentation existe. Les cases d’implémentation ou de tests locaux ne constituent pas une validation sur une instance domestique et des lampes réelles.

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
- [x] Définir la direction compacte du dashboard : pilotage prioritaire, liste/détail, sous-vues, accessibilité clavier et adaptation au thème Home Assistant.

## 3. Première version fonctionnelle

- [x] Construire le moteur Python par pièce, le stockage versionné et les commandes WebSocket authentifiées.
- [x] Ajouter le panneau embarqué TypeScript/Lit, les pièces Home Assistant, la sélection des lumières et les entités des appareils Halo.
- [x] Implémenter la présence, la luminosité, les pauses manuelles, la reprise et les transitions.
- [x] Implémenter l’ambiance de base, les profils naturels, leurs associations et les adaptations aux capacités des lampes.
- [x] Implémenter les scènes conditionnelles ordonnées, leur exposition dans Home Assistant et l’édition réelle avec restauration et expiration des sessions.
- [x] Ajouter les textes anglais et français, la langue par utilisateur et les états explicatifs du dashboard.
- [x] Refaire le panneau en liste/détail : recherche et commandes des pièces, cinq onglets, profils édités un à un, aides repliables et brouillon conservé entre sous-vues.
- [x] Suivre le thème Home Assistant pour les contrôles et la typographie, le mode clair/sombre et la réduction des mouvements, sans palette Halo indépendante.
- [x] Préserver l’édition native des lampes, les effets et scènes partielles, ainsi que l’import des scènes Home Assistant dans le brouillon.
- [x] Ajouter des tests automatisés des priorités, indisponibilités, accès concurrents, droits côté serveur, stockage et langues.
- [ ] Achever la validation de tous les scénarios d’acceptation de `PROJET.md` dans une instance Home Assistant avec le matériel cible.
- [x] Tester localement le rechargement, les pauses persistées, le déchargement, la désactivation et les changements d’état simulés, sans confondre les commandes Halo avec une intervention manuelle.
- [x] Vérifier plusieurs vues du panneau dans Chrome avec données simulées, en français/anglais, clair/sombre et sur mobile 375 × 812.
- [x] Vérifier la refonte à 390 et 1 436 pixels de large, en clair, sombre et thème personnalisé avec police à 125 %, et réussir les 52 tests frontend et le contrôle TypeScript.
- [x] Vérifier des parcours ciblés de la refonte dans Home Assistant 2026.10.0 isolé : scène partielle à deux lampes sur quatre, fenêtre native avec effet « Candle », annulation de session et import filtré jusqu’au brouillon puis à son abandon. Lampes simulées, aucune erreur console relevée pendant ces parcours.
- [ ] Valider sur une instance Home Assistant de test avec des lampes marche/arrêt, dimmables, à température de blanc et à couleur, y compris les transitions prises en charge ou absentes.
- [ ] Achever les essais domestiques d’installation, de langues et d’interactions avec les écrans, thèmes et équipements retenus ; les vérifications locales ciblées ne couvrent pas l’ensemble de ce jalon.
- [x] Actualiser les statuts dans `PROJET.md` et `DESIGN.md`, et présenter uniquement les fonctions réellement livrées comme disponibles dans le [README](../README.md).

## 4. Releases GitHub

Le 9 octobre 2026, Arnaud demande des releases GitHub pour distribuer des versions identifiables aux installations comme dépôt personnalisé HACS. Cette demande remplace le report initial de toute publication. Une release ne vaut ni validation complète du matériel ni activation dans le logement.

- [x] Mettre en place un workflow de release sur tag avec cohérence des versions, tests Python/frontend, bundle reproductible, Hassfest et validation HACS sans contrôle ignoré. Les tests locaux passent ; les résultats GitHub et la publication sont consignés séparément dans [DEVELOPMENT.md](DEVELOPMENT.md).
- [ ] Publier et vérifier la première release `v0.1.0`, accompagnée de ses limites de développement.
- [ ] Vérifier son installation et sa mise à jour comme dépôt personnalisé HACS dans une instance de test.

## 5. Référencement HACS, en dernier

- [ ] Achever les validations matérielles et suivre la [liste d’inclusion au catalogue](HACS.md#référencement-au-catalogue-en-dernier).
- [ ] Demander l’inclusion au catalogue HACS par défaut, puis vérifier son apparition après acceptation par les mainteneurs.
