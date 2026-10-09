# Halo — contexte produit

<!-- impeccable:product-schema 1 -->

Le cahier des charges détaillé reste [PROJET.md](PROJET.md). Ce résumé fournit le contexte de conception à Impeccable sans créer une seconde spécification fonctionnelle.

## Platform

web

## Users

Les habitants pilotent les lumières du logement. Les administrateurs Home Assistant configurent les pièces, les automatismes et les ambiances.

## Product Purpose

Une intégration unique centralise le pilotage et la configuration de toutes les lumières dans un panneau Home Assistant.

## Operating Context

Le panneau embarqué TypeScript/Lit communique avec le moteur Python. Celui-ci fonctionne sans dashboard ouvert. Le panneau suit la langue de l’utilisateur Home Assistant : français pour `fr` et ses variantes, anglais autrement.

## Capabilities and Constraints

Préserver toutes les fonctions existantes : appareils par pièce, lumières, modes, présence/luminosité, pause manuelle, ambiance de base, profils solaires, scènes conditionnelles, édition native des lampes, import de scènes, transitions et droits. Les changements passent par un brouillon et une sauvegarde avec contrôle de révision ; l’édition réelle suspend temporairement les automatismes de la pièce.

## Brand Commitments

Halo conserve son lotus monochrome. Les couleurs et les propriétés visuelles proviennent du thème Home Assistant, sans palette indépendante. La refonte demandée le 9 octobre 2026 doit être compacte, facile à utiliser et peut déplacer des options dans des sous-vues.

## Product Principles

- Pilotage des pièces en premier sur l’accueil, configuration accessible ensuite : confirmé par Arnaud le 9 octobre 2026.
- Aucune suppression de capacité existante lors de la refonte.
- États matériels distincts des intentions et commandes envoyées.
- Paramétrage réservé aux administrateurs ; contrôles serveur conservés.

## Evidence on Hand

Implémentation et tests dans le dépôt ; résultats et limites dans [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md). Les données de démonstration et les lampes locales de QA sont simulées. Ne pas présenter un aperçu ou un test local comme une validation sur les équipements du logement.
