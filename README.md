<p align="center">
  <img src="https://raw.githubusercontent.com/Gnol86/Halo/main/custom_components/halo/brand/icon@2x.png" alt="Lotus de Halo" width="144" height="144">
</p>

# Halo - Home Assistant Light Orchestrator

Halo centralise le pilotage et la configuration des lumières dans Home Assistant : présence, luminosité, ambiances naturelles, scènes et veilleuses, avec un panneau compact adapté au thème actif.

**Version 0.2.0 préparée :** pour les pièces sans capteur lumineux, choisis une autorisation permanente, une plage horaire ou la hauteur du soleil dans **Automatisation**. La veilleuse suit la même autorisation ; un capteur configuré reste prioritaire, même indisponible. Cet ajout est vérifié localement avec des lampes simulées, sans déploiement domestique. La publication suit le workflow de release ; son résultat sera consigné séparément. Consulte les [règles de fonctionnement](PROJET.md#autorisation-déclairage-sans-capteur-lumineux) et les [preuves et limites de validation](docs/QA-LIGHTING-FALLBACK-2026-10-10.md).

Installation : ajoute `https://github.com/Gnol86/Halo` comme dépôt personnalisé **Intégration** dans HACS. Home Assistant **2026.10.0 ou plus récent** est requis. Après une mise à jour, redémarre Home Assistant et recharge le navigateur. Les [notes de version 0.2.0](releases/0.2.0.md) présentent aussi les scènes liées et les veilleuses.
