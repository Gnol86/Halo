# Autorisation d’éclairage sans capteur — validation locale

Dernière mise à jour : **10 octobre 2026**.

## Périmètre et état

Ce rapport concerne uniquement l’ajout de `room.lighting_fallback` dans le checkout local de Halo. **Verdict : lot implémenté et vérifié localement**, avec **545 tests Python**, **95 tests frontend**, un bundle reproductible, des scénarios de services et un parcours graphique dans Home Assistant isolé avec des lampes simulées. Les décisions fonctionnelles figurent dans [PROJET.md](../PROJET.md#autorisation-déclairage-sans-capteur-lumineux), les interactions dans [DESIGN.md](../DESIGN.md) et le contrat de données dans [ARCHITECTURE.md](ARCHITECTURE.md#autorisation-déclairage-sans-capteur). La [recette transversale précédente](QA-2026-10-10.md) reste historique : ses anciens résultats ne sont pas réutilisés comme preuve automatique de cet ajout. Les scénarios effectivement réexécutés sur les nouvelles sources sont identifiés ci-dessous.

Le mode Toujours conserve le comportement sans capteur. L’horaire utilise le fuseau Home Assistant et une plage quotidienne début inclus / fin exclue ; le mode solaire compare strictement la hauteur au seuil du matin ou du soir. Un capteur configuré conserve la priorité, même indisponible. L’extinction normale est facultative ; les veilleuses s’éteignent toujours à la fermeture. Aucune donnée fictive en lux n’est produite.

## Matrice des cas

« Réussi — test » désigne une exécution automatisée, pas une observation matérielle. « À vérifier » signifie qu’aucune preuve d’exécution propre à ce lot n’est encore enregistrée ici. Plusieurs cas peuvent être couverts par un même test ; les nombres de cas et de tests ne s’additionnent pas.

| Cas | Critère | Situation et résultat attendu | Preuve / état |
| --- | --- | --- | --- |
| LF01 | A69 | Ancienne configuration sans champ : défaut Toujours, autres valeurs intactes, aucune mutation de l’objet fourni ou d’une autre pièce. | Réussi — `test_legacy_fallback_is_always_and_never_mutates_supplied_config` dans [test_lighting_fallback_config.py](../tests/test_lighting_fallback_config.py). |
| LF02 | A69 | Modes, types, clés, heures, booléens et seuils invalides rejetés ; heures identiques refusées même dans un mode inactif. | Réussi — `test_invalid_fallback_is_rejected_even_when_inactive` (cas paramétrés). |
| LF03 | A69 | Trois modes, seuils signés/décimaux et valeurs inactives conservés ; bornes solaires −90° et 90° acceptées. | Réussi — `test_all_modes_preserve_inactive_choices_and_signed_fractional_elevations`. |
| LF04 | A69, A72 | Sauvegarde puis ajout/retrait d’un capteur et rechargement : réglages alternatifs préservés. | Réussi — `test_api_roundtrip_keeps_fallback_across_sensor_changes_and_reload` via le WebSocket Home Assistant de test. |
| LF05 | A69 | Écriture invalide, révision périmée, erreur disque et non-administrateur : refus sans modifier la politique active. | Réussi — `test_invalid_conflicting_failed_and_non_admin_saves_leave_policy_unchanged`. |
| LF06 | A70 | Plage diurne et plage passant minuit, début inclus, fin exclue, fuseau local Home Assistant. | Réussi — `test_schedule_opens_at_exact_local_minute_without_new_presence`, `test_overnight_schedule_inclusive_start_exclusive_end`. |
| LF07 | A70 | Ouverture et fermeture déclenchées à leur échéance, sans attendre la scrutation ; fuseau/changements d’heure et horloge de test maîtrisés. | Réussi — test d’ouverture à la minute et `test_schedule_follows_local_clock_across_dst_jump` (printemps/automne, Europe/Brussels) ; ouverture/fermeture aux minutes réelles dans Home Assistant isolé. |
| LF08 | A71 | Soleil sous, égal et au-dessus du seuil ; matin/soir liés puis séparés, décimales. | Réussi — `test_solar_strict_threshold_opens_once_and_closes_after_confirmation`, `test_separate_solar_thresholds_require_a_boolean_direction`. |
| LF09 | A71, A72 | Soleil ou attribut requis absent, invalide ou indisponible ; rétablissement sans hauteur zéro inventée. | Réussi — `test_invalid_solar_elevation_never_becomes_dark`, `test_missing_solar_entity_blocks_without_falling_back_to_always`, `test_invalid_solar_data_leaves_an_active_natural_ambience_unchanged` et tests frontend hauteur/direction. |
| LF10 | A72 | Capteur configuré clair/sombre puis indisponible, malgré une autorisation horaire/solaire opposée. | Réussi — `test_configured_lux_always_takes_precedence_even_when_unavailable` ; persistance couverte par LF04. |
| LF11 | A73 | Fermeture horaire : extinction normale immédiate uniquement si activée ; mode Toujours sans fermeture. | Réussi — `test_schedule_closing_only_switches_off_when_requested`, `test_always_keeps_legacy_permission_without_claiming_a_lux_measurement`. |
| LF12 | A73 | Fermeture solaire continue : délai `lux_off_delay`, réouverture annulant le délai, extinction unique. | Réussi — tests solaire strict et `test_solar_confirmation_cancels_on_permission_or_unknown_input`. |
| LF13 | A74 | Veilleuse pendant une absence confirmée : ouverture déclenchant les seules veilleuses, fermeture les éteignant malgré `turn_off=false`. | Réussi — `test_nightlight_follows_permission_even_without_normal_off` (horaire et soleil) ; veilleuse solaire avec effet Candle et retour à l’ambiance complète dans Home Assistant isolé. |
| LF14 | A74 | Retour de présence depuis une veilleuse : ambiance normale complète si autorisée, sinon attente. | Réussi — `test_nightlight_returns_full_natural_ambience_on_presence` ; veilleuse éteinte à la fermeture couverte par LF13. Le cas à une lampe reste couvert par les tests historiques de veilleuse, pas par un nouveau parcours du panneau. |
| LF15 | A73, A74 | Transitions : présence `turn_on`, ouverture horaire/solaire `lux_on`, fermeture `turn_off` ; valeurs héritées/locales respectées. | Réussi — assertions de catégorie dans les tests ouverture/fermeture, soleil strict, retour de présence et reprise naturelle après veilleuse. Héritage/localité couverts par les tests généraux des transitions. |
| LF16 | A75 | Scène autonome prioritaire, pause manuelle avec les deux choix d’extinction, édition et automatisation désactivée. | Réussi — `test_autonomous_scenes_keep_priority_and_regular_scenes_wait`, `test_manual_pause_disabled_and_editor_remain_authoritative`, `test_nightlight_solar_open_respects_manual_pause_policy`. |
| LF17 | A75 | Commandes lentes, intention manuelle plus récente, fermeture/réouverture et réévaluations répétées. | Réussi — `test_schedule_closing_interrupts_pending_automatic_on_before_lock`, `test_fallback_change_does_not_interrupt_newer_manual_command`, `test_reopening_cancels_slow_off_and_reapplies_full_ambience_with_lux_on`. |
| LF18 | A75 | Reconfiguration et redémarrage : recalcul des autorisations/échéances et préservation de la pause. | Réussi — `test_restart_recomputes_permission_and_restores_pause`, `test_reconfiguration_discards_previous_solar_confirmation` ; rechargement des paramètres couvert par LF04. |
| LF19 | A76 | Formulaire conditionnel, capteur prioritaire, erreurs révélées, sauvegarde/abandon et valeurs masquées préservées. | Réussi — tests frontend des défauts/masquage, changements de mode et validations horaire/solaire ; parcours réel sur ordinateur : seuil du soir conservé après liaison, heures identiques refusées avec focus, correction sauvegardée et seuils conservés au retour solaire. |
| LF20 | A76 | Source, autorisation et échéance lisibles, sans valeur lux fictive ; français/anglais, clavier, mobile et thème Home Assistant. | Réussi — tests frontend du soleil courant, de l’état traduit et de l’aide veilleuse ; confirmation solaire affichée uniquement pour la source solaire. Observations françaises avec thème sombre à 1 440, 768 et 375 px, focus Tab et barre de sauvegarde ; anglais vérifié automatiquement seulement. |
| LF21 | A75 | Retour rapide après extinction pour absence, autorisation se fermant avant le retour ; fermeture pendant une commande lente. | Réussi — `test_presence_inside_window_uses_turn_on_and_quick_return_cannot_escape_it`, complété par la concurrence LF17 ; aucune dérogation à une autorisation alternative fermée ou indisponible. |
| LF22 | A72, A75 | Après retrait du capteur, un ancien `lux_off=true` ne bloque pas le retour rapide autorisé, même pendant le fondu ou des extinctions en attente. | Réussi — `test_inactive_lux_off_does_not_prevent_return_during_fade` (quatre cas) et `test_inactive_lux_off_does_not_leave_pending_absence_commands` ; essai ciblé après redémarrage de Home Assistant isolé, quatre commandes de présence à transition zéro. Comportement avec véritable capteur conservé. |

## Exécutions consignées

- **Modèle et API : 24 tests ciblés réussis**, dans `tests/test_lighting_fallback_config.py`. Les tests API utilisent les services et WebSocket du harness Home Assistant avec stockage, permissions et rechargement. Cela ne constitue pas un parcours du panneau dans un navigateur.
- **Moteur : 306 tests élargis réussis en 3,60 secondes**, dont **57 cas dédiés** répartis dans 25 fonctions de [test_lighting_fallback_engine.py](../tests/test_lighting_fallback_engine.py). Une dernière régression corrige l’influence de `lux_off` inactif sur un retour rapide après retrait du capteur : quatre cas d’abord en échec, puis corrigés, complétés par une séquence d’extinctions en attente.
- **Suite Python finale : 545 tests réussis en 8,90 secondes.** `uv sync --frozen`, Ruff et format conformes (62 fichiers). Les lots ciblés et le total ne doivent pas être additionnés.
- **Frontend final : TypeScript et 95 tests réussis**, dont huit régressions propres à ce lot dans [panel.test.ts](../frontend/tests/panel.test.ts). Installation `npm ci` sous Node.js **24.21.0**. Champs horaires `HH:MM`, hauteur solaire dans les bornes physiques, valeurs numériques textuelles valides et direction manquante explicitement traités. Le dernier test d’échéance garantit qu’une source horaire n’affiche pas une fausse confirmation solaire.
- **Bundle final reconstruit deux fois à l’identique :** SHA-256 `2ed6d4f7d593efcebfa12dc66a484ec76312e39b24f72b762258c03e7794640c`.
- **Home Assistant isolé : 11 scénarios de services réussis** avec capteurs et lampes simulés ; détail ci-dessous. Cette exécution précède la dernière correction ciblée de retour rapide LF22.
- **Interface réelle : parcours en français avec thème Home Assistant sombre**, sur ordinateur, tablette et mobile, détaillé ci-dessous. Anglais couvert automatiquement ; aucune inspection visuelle anglaise ni audit d’accessibilité exhaustif revendiqué.

Les traces finales sont `tmp/fallback-python-full.log`, `tmp/fallback-frontend-check.log`, `tmp/fallback-frontend-tests.log` et `tmp/fallback-bundle.sha`, exclues de Git. Aucune case non exécutée n’est considérée réussie sur la seule lecture du code.

La trace frontend est `tmp/lighting-fallback-frontend-tests.log`, exclue de Git. Les huit tests couvrent :

- `lighting fallback defaults are detached, legacy-safe and hidden whenever a lux sensor is configured` ;
- `lighting fallback mode changes preserve inactive hours, solar thresholds and normal shutoff in the saved draft` ;
- `fallback time range rejects equal or empty times before save, navigation or hiding the fields` ;
- `fallback solar fields validate bounds, preserve invalid input and expose confirmation for nightlights independently of normal shutoff` ;
- `fallback sun elevation follows the global live entity without invented zero or stale readings and keeps drafts untouched` ;
- `separate fallback solar thresholds report a missing direction without hiding a valid elevation` ;
- `lighting authorization and solar deadline are localized from engine status without implying a lux reading` ;
- `fallback configuration and nightlight guidance follow locale while retaining private drafts and shared settings`.

## Parcours dans Home Assistant isolé

Les 11 scénarios exécutés utilisent Home Assistant **2026.10.0**, son frontend officiel **20260930.2** et l’instance locale `127.0.0.1:18123`. Ils pilotent quatre lampes simulées dans Atelier QA, une présence, une mesure lumineuse et un soleil simulés. Les identifiants internes du script préfixés `LF` ne sont pas ceux de la matrice documentaire ci-dessus ; le tableau donne la correspondance par comportement.

| Scénario exécuté | Résultat | Cas documentaire lié |
| --- | --- | --- |
| Ancienne configuration, mode Toujours et présence | Réussi | LF01, LF11 |
| Soleil passant strictement sous le seuil pendant la présence ; transition `lux_on`, aucune relance à la mesure suivante, `lux: null` | Réussi | LF08, LF15, LF20 |
| Seuils distincts matin/soir et changement de branche | Réussi | LF08 |
| Égalité au seuil, début de confirmation, annulation lors d’une réouverture puis extinction confirmée | Réussi | LF12 |
| Extinction normale désactivée : maintien après fermeture, extinction sur absence puis refus d’un nouvel allumage hors autorisation | Réussi | LF11, LF21 |
| Veilleuse seule avec effet **Candle**, retour présent réappliquant les quatre lampes, nouvelle absence et extinction solaire | Réussi | LF13, LF14 |
| Soleil indisponible puis direction manquante, rétablissement sans mesure zéro inventée | Réussi | LF09 |
| Capteur configuré inconnu malgré soleil favorable ; capteur sombre malgré soleil défavorable | Réussi | LF10 |
| Commande manuelle hors autorisation et pause, puis extinction manuelle conservée à la réouverture | Réussi | LF16 |
| Plage d’une minute sur l’horloge réelle Europe/Brussels, ouverture sans nouvel événement de présence, fermeture immédiate malgré confirmation réglée à 300 s | Réussi ; parcours de 85,329 s, fermeture constatée en moins de 3 s après la borne | LF07, LF11, LF15 |
| Rechargement de l’intégration, réglages préservés et décision solaire recalculée | Réussi | LF04, LF18 |

Les preuves temporaires sont `tmp/halo-native-qa/fallback_qa.py`, `fallback-results.json` et `fallback-probe-final.log`. Le démarrage initial du banc depuis un mauvais répertoire ne chargeait pas les lampes simulées : son répertoire de travail a été corrigé avant ces résultats. Un premier contrôle de fermeture lisait l’instantané avant le traitement de l’événement ; le test attend désormais l’autorisation observée avant de vérifier le délai. Ces ajustements du banc ne sont pas attribués à un défaut de Halo.

Après la correction du retour rapide avec `lux_off` inactif, l’instance est redémarrée sur les sources Python finales. Les **15 scénarios de services de la recette antérieure sont réexécutés et réussissent** : présence/absence, hystérésis, retour rapide, indisponibilités, pauses, désactivation, veilleuse, scènes/import/liens, droits/révisions, édition, profils naturels, états personnalisés et rechargement. Il s’agit d’une nouvelle exécution sur le lot courant, consignée dans `tmp/halo-native-qa/fallback-regression-probe.log` et `full-qa-results.json`.

Un **essai ciblé final LF22 réussit** : sans capteur, `lux_off=true` conservé et retour avant 30 secondes, quatre commandes `turn_on` utilisent la transition de présence **0 s**. Les preuves sont `tmp/halo-native-qa/fallback-final-return.log` et `fallback-final-return.json`. Les 11 scénarios nouveaux précèdent seulement cette correction ciblée ; les 15 régressions et cet essai final suivent le redémarrage.

## Parcours d’interface

Dans le navigateur relié à cette instance, sur ordinateur, le panneau affiche le soleil à **−8°**, montant, et les seuils **−6° / 2°**. Lier puis délier conserve le seuil du soir à 2°. Le mode horaire présente **18:00–08:00** ; la saisie **18:00–18:00** bloque la sauvegarde et place le focus sur l’heure de fin. Corriger en 08:00 permet l’enregistrement. Revenir au mode solaire conserve −6° / 2°, puis la sauvegarde réussit. Ces manipulations valident le formulaire réel et sa persistance, en complément des tests frontend.

Le rendu réel est examiné en français, dans le thème Home Assistant sombre, à **1 440 × 1 000**, **375 × 812** et **768 × 1 024**. Les champs solaires passent sur une colonne mobile ; les largeurs utiles/défilantes mesurées sont **375/375** et **768/768**, sans débordement horizontal. Sur mobile, changer la fin de plage de 08:00 à 07:30 conserve les deux boutons lisibles dans la barre fixe. Abandonner rétablit le mode solaire et les seuils −6° / 2°. Le passage par Tab depuis le choix de mode vers la case de liaison garde un focus visible.

L’autorisation apparaît sur sa propre ligne, séparée de l’état physique allumé/éteint ; une échéance horaire n’est pas étiquetée comme une confirmation solaire. Ces deux ajustements ont été intégrés avant le build final. Captures temporaires : `tmp/fallback-desktop-solar.jpg`, `tmp/fallback-desktop-status.jpg`, `tmp/fallback-mobile-solar.jpg` et `tmp/fallback-mobile-time.jpg`.

Aucune nouvelle erreur console n’est relevée depuis le chargement du build final, vers 00:49 UTC. Six anciennes entrées `Object` de 00:43–00:47 restent non qualifiées : la console entière n’est donc pas déclarée vierge. Le journal serveur final ne relève pas d’erreur Halo avant arrêt ; il contient les avertissements d’intégration personnalisée et de caméra sans TurboJPEG. L’anglais est vérifié par les tests automatisés, sans inspection visuelle anglaise ; le parcours clavier ciblé ne constitue pas un audit d’accessibilité exhaustif.

En clôture, l’automatisation Atelier QA est désactivée via le panneau, l’onglet de test est fermé et le viewport est restauré. L’instance locale est arrêtée par `SIGTERM` et le port **18123** est vérifié fermé. Le code de sortie **139** après ce signal, déjà observé avec ce banc macOS/Python, empêche de qualifier l’arrêt du processus de propre ; aucun défaut applicatif Halo n’a été observé dans son journal avant arrêt.

## Limites

Le rapport ne couvre aucun capteur ni lampe du logement. Les variations saisonnières réelles, les particularités des intégrations solaires, les transitions physiques et les remontées des appareils exigent des essais matériels distincts. Aucun déploiement domestique, push, tag ou publication n’est inclus dans cette validation locale.
