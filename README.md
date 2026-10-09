<p align="center">
  <img src="https://raw.githubusercontent.com/Gnol86/Halo/main/custom_components/halo/brand/icon@2x.png" alt="Lotus de Halo" width="144" height="144">
</p>

# Halo

Une intégration Home Assistant destinée à gérer l’ensemble des lumières du logement.

**Statut : première version de développement.** Halo dispose d’un panneau embarqué, d’appareils par pièce et d’un moteur d’éclairage. La refonte compacte est implémentée et vérifiée localement, avec des aperçus adaptatifs et des parcours ciblés dans Home Assistant 2026.10.0 isolé utilisant des lampes simulées. La validation complète dans une instance domestique et avec des lampes réelles reste à réaliser. Ces vérifications ne constituent pas un déploiement dans le logement. La publication et le référencement dans HACS sont prévus à la fin du projet.

## Ce qui existe

- Structure d’une intégration personnalisée dans `custom_components/halo/`.
- Configuration depuis l’interface, avec une seule instance par logement.
- Chargement, déchargement et rechargement de l’intégration.
- Textes en français et en anglais, icône de lotus embarquée.
- Tests avec Home Assistant et workflows de validation préparés.

**Icône dans HACS :** HACS 2.0.5 affiche encore une image de remplacement dans sa liste pour les nouvelles intégrations comme Halo. Les fichiers du lotus sont bien embarqués pour Home Assistant ; l’image de présentation de ce README utilise une URL absolue indépendante de cette limite. Le [diagnostic et le correctif attendu côté HACS](docs/HACS.md#affichage-du-lotus) sont documentés.

## Première implémentation fonctionnelle

Les comportements retenus sont détaillés dans [PROJET.md](PROJET.md), et les règles d’interface dans [DESIGN.md](DESIGN.md). Le code et le panneau comprennent maintenant :

- Un panneau **Halo** ajouté automatiquement à la barre latérale après l’installation unique, pour toute la configuration ; pilotage accessible aux utilisateurs et configuration réservée aux administrateurs.
- Un lotus monochrome natif dans la barre latérale et l’en-tête, suivant le thème Home Assistant ; l’en-tête Halo ne comporte pas de bouton de menu supplémentaire.
- Un panneau compact centré sur le pilotage : liste recherchable des pièces et commandes rapides à gauche, détail à droite sur ordinateur ; liste puis détail sur mobile. Les cinq onglets d’une pièce organisent le pilotage, les lumières, l’automatisation, les ambiances et les réglages. Les pièces configurées dans le brouillon courant apparaissent avant les autres, en conservant l’ordre fourni par Home Assistant dans chaque catégorie, même pendant la recherche.
- Une vue dédiée aux profils naturels, avec un seul profil à éditer à la fois ; l’entité soleil et les transitions par défaut sont dans les réglages globaux. Les aides et réglages détaillés se déplient au besoin.
- Les pièces de Home Assistant, avec sélection explicite des lumières et un appareil par pièce regroupant la commande d’éclairage, les modes automatique et naturel, la reprise et les scènes.
- La recherche par nom ou identifiant dans les sélecteurs d’entités et les listes de lampes, avec indication des groupes Home Assistant, y compris Philips Hue, et des appartenances connues. Certains groupes Hue n’exposent pas leurs membres.
- Dans l’onglet **Lumières**, les lampes des autres pièces sont masquées par défaut et accessibles avec **« Afficher les lumières des autres pièces »**, y compris les lampes sans pièce. Les lampes déjà sélectionnées restent visibles dans un groupe distinct si elles sont rattachées ailleurs. La recherche respecte ce filtre temporaire, sans modifier la configuration ; le changement de pièce ou le rechargement le réinitialise.
- Une barre d’enregistrement toujours visible au bas du panneau pendant le défilement, un brouillon conservé entre sous-vues et une validation avant de quitter un champ incorrect. Les repères graphiques suivent les hauteurs solaires configurées et les champs de transition restent alignés.
- L’allumage et l’extinction selon la présence et la luminosité, avec seuil, hystérésis et temporisations configurables.
- Une pause après une commande manuelle, avec une option par pièce pour maintenir les extinctions automatiques pendant cette pause.
- Des profils de lumière naturelle fondés sur l’élévation du soleil, associables à plusieurs groupes dans une même pièce, avec courbes de luminosité et de température de blanc adaptées aux lampes compatibles. Chaque courbe peut être **linéaire** ou à **accélération et décélération progressives**, avec aperçu en S et arrivée douce aux deux limites. Les anciennes sélections d’accélération adoptent ce comportement corrigé ; les profils sans type explicite restent linéaires.
- Une ambiance de base et des scènes conditionnelles prioritaires, ordonnées dans le dashboard, avec édition en direct sur les lampes pendant la suspension de l’automatisation de la pièce.
- Des transitions par type de changement, définies globalement et personnalisables ou désactivables par pièce.
- L’anglais comme langue de référence, une traduction française suivant la langue de l’interface Home Assistant et un repli en anglais pour les autres langues. Les noms personnalisés restent inchangés.

Les pièces nouvellement configurées ont leurs automatismes **désactivés** jusqu’à leur activation. La direction retenue est une interface compacte suivant le thème Home Assistant : couleurs et états, police, tailles, espacements, bordures, rayons, en-tête et champs, avec des valeurs de repli si nécessaire. Le mode clair/sombre et la préférence de mouvement réduit sont respectés, sans palette propre à Halo. Les étapes de validation figurent dans la [feuille de route](docs/ROADMAP.md).

**Capteur d’état par pièce : implémenté.** Dans l’appareil de chaque pièce, le capteur **État** (`Status`) indique **Éteint**, **Manuel**, **Lumière naturelle** ou le nom de la scène active. Les états fixes sont traduits en français et en anglais ; les noms de scène ne sont pas traduits. Il suit les événements même sans panneau ouvert et devient indisponible si aucune lampe n’est disponible. Une extinction réelle prime sur le mode ; une scène lancée explicitement reste nommée pendant sa pause, même si les automatismes sont désactivés. Des tests locaux du moteur et des plateformes Home Assistant utilisent des lampes simulées ; les essais dans le navigateur et sur les équipements du logement restent à faire pour cet ajout. Le statut détaillé du panneau reste disponible.

Les nouveaux réglages proposent **0 seconde** de délai d’absence et **120 minutes** de pause manuelle. Les transitions globales initiales sont **0 s** à l’allumage, **10 s** après baisse de luminosité, **60 s** pour la lumière naturelle, **10 s** pour les scènes et **2 s** à l’extinction ; les pièces en héritent. Les valeurs déjà enregistrées sont conservées. Le seuil et l’hystérésis affichent l’unité du capteur (`lx`, `%`, etc.), sans conversion implicite. La création des profils et des scènes est compatible avec un accès local en HTTP.

**Rallumage rapide après absence : implémenté et testé localement.** Une fenêtre globale de **30 secondes**, réglable dans **Réglages globaux** et désactivable par **0**, permet de rallumer sans attendre une mesure lumineuse encore trop élevée après l’extinction automatique pour absence. Elle concerne uniquement les pièces sans extinction sur forte luminosité et utilise la transition d’allumage habituel. Les pauses, l’édition et la désactivation des automatismes restent respectées ; une extinction manuelle n’ouvre pas cette fenêtre. Les anciennes configurations sans ce réglage reçoivent 30 secondes, sans remplacer les valeurs explicitement enregistrées. La validation sur les lampes du logement et le déploiement domestique restent à réaliser pour cet ajout.

**Protection du mode manuel contre les brèves absences : implémentée et testée localement.** La même durée globale de **30 secondes** protège aussi la pause manuelle dans toutes les pièces. Le retour de présence ne la termine qu’après une absence continue atteignant la plus grande durée entre ce réglage et le délai d’absence de la pièce. Un retour plus tôt conserve la pause ; une indisponibilité du détecteur interrompt le décompte d’absence continue. **0** retire seulement ce minimum supplémentaire, sans changer le délai d’absence. L’extinction automatique, l’expiration propre de la pause et le bouton de reprise gardent leur fonctionnement habituel. Une pause encore active bloque le rallumage rapide, sans restauration automatique d’une ambiance manuelle. La validation matérielle et le déploiement domestique restent à réaliser pour cet ajout.

Les transitions dépendent des capacités annoncées par chaque lampe. Sur les équipements qui ne restituent pas le contexte des commandes, la distinction entre une transition et une intervention physique repose sur les changements d’état observés et doit encore être vérifiée sur le matériel utilisé.

**Édition native des scènes :** un clic sur une lampe dans Halo ouvre sa véritable fenêtre Home Assistant. La scène conserve les réglages reproductibles remontés par la lampe, effets compris, ainsi que les canaux blancs RGBW/RGBWW. Les options propriétaires non exposées à Home Assistant ne peuvent pas être récupérées. Ce parcours utilise l’action documentée de Home Assistant, sans dépendance aux composants privés de son éditeur. Il a été vérifié dans une instance Home Assistant locale avec le frontend officiel et des lampes simulées ; les essais sur les équipements du logement restent à faire.

Les sélecteurs d’entités restent ceux de Halo. Leur remplacement par le sélecteur natif est demandé mais non implémenté : aucun chargement public fiable pour le panneau personnalisé n’a été identifié. La [limite et les voies natives disponibles](docs/ARCHITECTURE.md#sélecteurs-dentités-natifs) sont documentées.

**Import de scènes Home Assistant :** depuis les scènes d’une pièce, un administrateur peut rechercher une scène enregistrée, vérifier les lampes retenues et renommer la copie avant de l’ajouter au brouillon. Seules les lampes sélectionnées dans la pièce Halo sont copiées, effets compris. La copie est indépendante, sans commande aux lampes pendant l’import ou sa sauvegarde ; les lampes absentes restent inchangées au lancement et à la réédition. L’import repose sur les scènes dans `scenes.yaml` avec un identifiant ; les scènes temporaires et celles d’intégrations tierces sans configuration accessible ne sont pas prises en charge. Le parcours est vérifié dans Home Assistant 2026.10.0 isolé avec des lampes simulées ; les essais sur les équipements du logement restent à faire.

## Essai manuel en développement

Les nouveaux profils naturels démarrent avec **40 % à −20° → 100 % à 20°** pour la luminosité et **2 000 K à 0° → 5 500 K à 20°** pour la température, en linéaire avec matin et soir liés. Les profils déjà enregistrés conservent leurs valeurs.

La version de référence et le minimum déclaré sont **Home Assistant 2026.10.0**. La compatibilité avec les versions précédentes n’est pas revendiquée.

1. Copier le dossier `custom_components/halo` dans le dossier `custom_components` de la configuration d’une instance de test Home Assistant.
2. Redémarrer cette instance pour qu’elle découvre les fichiers.
3. Ouvrir **Paramètres → Appareils et services → Ajouter une intégration**.
4. Rechercher **Halo**, puis confirmer la configuration.

5. Ouvrir **Halo** dans la barre latérale, choisir une pièce puis **Configurer la pièce**. Sélectionner ses lampes dans **Lumières** et enregistrer. La configuration est réservée aux administrateurs.
6. Vérifier les commandes de la pièce. Renseigner les capteurs dans **Automatisation**, créer les profils dans **Profils de lumière naturelle**, puis les associer dans **Ambiances**. Activer les automatismes lorsque les réglages sont prêts.

Le dossier à copier contient déjà le bundle du panneau ; aucune compilation ni carte supplémentaire n’est nécessaire dans Home Assistant. Après remplacement du bundle pendant le développement, recharger également la page du navigateur. Pour retirer Halo, supprimer son entrée dans **Appareils et services**, puis son dossier si nécessaire.

## Développement

Avec [uv](https://docs.astral.sh/uv/) installé :

```sh
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
```

Pour modifier le panneau, utiliser Node.js 24 et npm :

```sh
npm ci
npm run check
npm test
npm run build
```

Le bundle généré doit accompagner toute modification des sources TypeScript. Le [guide du panneau](frontend/README.md) fournit un aperçu local avec des données simulées.

Le fichier `.python-version` fixe Python 3.14.5 ; `uv.lock` fixe les dépendances des tests. Aucune dépendance Python externe n’est requise par Halo dans l’instance Home Assistant.

Ce README, `PROJET.md` et `DESIGN.md` sont maintenus à jour en temps réel. Toute évolution doit être répercutée dans les documents concernés au cours de la même tâche, selon les consignes d’`AGENTS.md`.

- [Consignes pour les agents](AGENTS.md)
- [Projet et fonctionnalités](PROJET.md)
- [Design du dashboard](DESIGN.md)
- [Conventions de développement](docs/DEVELOPMENT.md)
- [Architecture et API du panneau](docs/ARCHITECTURE.md)
- [Documentation HACS étudiée et publication future](docs/HACS.md)
- [Feuille de route](docs/ROADMAP.md)
- [Icône et source graphique](assets/branding/README.md)

## Licence

[MIT](LICENSE).
