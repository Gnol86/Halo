# Feuille de route

Dernière mise à jour : **10 octobre 2026**.

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

- [x] Définir la veilleuse par pièce dans Ambiances : lampes fixes pendant l’absence, seuils communs, priorité des scènes autonomes, pauses et édition native, sans sixième onglet.
- [x] Définir l’autorisation d’éclairage sans capteur par pièce : Toujours, plage horaire locale ou seuil solaire, capteur configuré prioritaire même indisponible et fermeture systématique des veilleuses. Décision du 10 octobre 2026.

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
- [x] Définir le lancement de scènes Home Assistant liées : source native complète, mêmes règles et priorités, avertissements de périmètre et tolérance temporaire des retours sans contexte. Décision du 10 octobre 2026, distincte de l’import d’une copie filtrée.
- [x] Implémenter les scènes liées : modèle compatible, inspection administrateur, lancement natif et repli, droits et récursion, menu d’ajout, formulaire de lien et traductions. Contrats dans `PROJET.md` et `ARCHITECTURE.md`.
- [x] Vérifier les scènes liées : tests Python/frontend avec sources natives et opaques simulant Hue, avertissements, effets, transitions, priorité manuelle et tolérance, erreurs, droits et révisions ; parcours natif dans Home Assistant isolé avec lampes simulées. Résultats dans `DEVELOPMENT.md` ; les essais sur un pont Hue réel restent à faire.
- [x] Ajouter des tests automatisés des priorités, indisponibilités, accès concurrents, droits côté serveur, stockage et langues.
- [x] Implémenter la veilleuse dans Ambiances, les réglages persistés compatibles, la capture dédiée, le mode d’état et les protections du moteur. Ajout du 10 octobre 2026, sans sixième onglet.
- [x] Vérifier la veilleuse : moteur et API, effets/couleurs, pauses/redémarrage, groupes et édition ; parcours sur ordinateur dans Home Assistant 2026.10.0 isolé avec lampes simulées. Suite complète : 437 tests Python et 73 tests frontend réussis ; preuves dans `DEVELOPMENT.md`.
- [x] Vérifier la veilleuse dans Home Assistant isolé à 1 280 × 720 et 390 × 844 : section activée, édition et fenêtre native avec effet, sélection préservée, annulation/restauration, lien vers Automatisation et absence de débordement du panneau. Vérifier aussi le mode d’état sans capteur lumineux et la conservation du blocage manuel après rechargement. Preuves dans `DEVELOPMENT.md` ; aucun essai matériel du logement.
- [x] Mener une recette transversale locale avec capteurs de présence/luminosité/soleil et lampes simulés ; inventorier les 68 critères, croiser tests moteur/API/frontend et parcours Home Assistant isolé, puis corriger les régressions prouvées. La matrice et les limites figurent dans [QA-2026-10-10.md](QA-2026-10-10.md) ; ce résultat ne vaut pas 68 essais matériels ni une publication.
- [x] Implémenter `lighting_fallback`, les échéances horaires et solaires, les protections moteur et les réglages conditionnels dans Automatisation. Valeurs inactives préservées et statut distinct d’une mesure en lux ; retour rapide sans influence d’un ancien réglage `lux_off` après retrait du capteur.
- [x] Valider localement ce lot avec les critères A69–A76 : **545 tests Python**, **95 tests frontend**, bundle reproductible, **11 nouveaux scénarios** dans Home Assistant isolé, puis **15 régressions** et un retour rapide ciblé après le dernier correctif. Parcours graphique en français sur ordinateur/mobile, limites dans [QA-LIGHTING-FALLBACK-2026-10-10.md](QA-LIGHTING-FALLBACK-2026-10-10.md). Lampes simulées ; aucune publication ni validation matérielle déduite.
- [ ] Achever la validation de tous les scénarios d’acceptation de `PROJET.md` dans une instance Home Assistant avec le matériel cible.
- [x] Tester localement le rechargement, les pauses persistées, le déchargement, la désactivation et les changements d’état simulés, sans confondre les commandes Halo avec une intervention manuelle.
- [x] Vérifier plusieurs vues du panneau dans Chrome avec données simulées, en français/anglais, clair/sombre et sur mobile 375 × 812.
- [x] Vérifier la refonte à 390 et 1 436 pixels de large, en clair, sombre et thème personnalisé avec police à 125 %, et réussir les 52 tests frontend et le contrôle TypeScript.
- [x] Vérifier des parcours ciblés de la refonte dans Home Assistant 2026.10.0 isolé : scène partielle à deux lampes sur quatre, fenêtre native avec effet « Candle », annulation de session et import filtré jusqu’au brouillon puis à son abandon. Lampes simulées, aucune erreur console relevée pendant ces parcours.
- [ ] Valider sur une instance Home Assistant de test avec des lampes **physiques** marche/arrêt, dimmables, à température de blanc et à couleur, y compris les transitions prises en charge ou absentes ; les capacités simulées font partie de la recette locale ci-dessus.
- [ ] Achever les essais domestiques d’installation, de langues et d’interactions avec les écrans, thèmes et équipements retenus ; les vérifications locales ciblées ne couvrent pas l’ensemble de ce jalon.
- [x] Actualiser les statuts dans `PROJET.md` et `DESIGN.md`, et présenter uniquement les fonctions réellement livrées comme disponibles dans le [README](../README.md).

## 4. Releases GitHub

Le 9 octobre 2026, Arnaud demande des releases GitHub pour distribuer des versions identifiables aux installations comme dépôt personnalisé HACS. Cette demande remplace le report initial de toute publication. Une release ne vaut ni validation complète du matériel ni activation dans le logement.

- [x] Mettre en place un workflow de release sur tag avec cohérence des versions, tests Python/frontend, bundle reproductible, Hassfest et validation HACS sans contrôle ignoré. Les tests locaux passent ; les résultats GitHub et la publication sont consignés séparément dans [DEVELOPMENT.md](DEVELOPMENT.md).
- [x] Publier et vérifier la première [release `v0.1.0`](https://github.com/Gnol86/Halo/releases/tag/v0.1.0), accompagnée de ses limites de développement : publication le 9 octobre 2026, six jobs du workflow réussis dont HACS/Hassfest, archive GitHub contrôlée.
- [x] Publier et vérifier [v0.2.0](https://github.com/Gnol86/Halo/releases/tag/v0.2.0) le 10 octobre 2026 : six jobs de release réussis, 28 fichiers distribuables comparés au tag, sans déploiement domestique.
- [ ] Vérifier son installation et sa mise à jour comme dépôt personnalisé HACS dans une instance de test.

## 5. Référencement HACS, en dernier

- [ ] Achever les validations matérielles et suivre la [liste d’inclusion au catalogue](HACS.md#référencement-au-catalogue-en-dernier).
- [ ] Demander l’inclusion au catalogue HACS par défaut, puis vérifier son apparition après acceptation par les mainteneurs.
