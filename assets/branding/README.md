# Lotus de Halo

Première proposition : un lotus à cinq pétales, aux tons chauds, dont le pétale central évoque une flamme. Image générée le 9 octobre 2026 avec l’outil intégré `image_gen`, à partir de la demande de fleur de lotus.

- `lotus-source.png` : source générée, conservée sans modification.
- `../../custom_components/halo/brand/icon.png` : PNG transparent, 256 × 256.
- `../../custom_components/halo/brand/icon@2x.png` : PNG transparent, 512 × 512.

Les exports sont de simples redimensionnements de la source, réalisés avec `sips`. Les mêmes couleurs sont utilisées en thèmes clair et sombre ; leur rendu dans l’interface Home Assistant reste à vérifier visuellement. Le symbole seul sert aussi de logo via le mécanisme de repli de Home Assistant.

[Dimensions des icônes](https://github.com/home-assistant/brands#image-specification) · [Images locales des intégrations personnalisées](https://developers.home-assistant.io/docs/core/integration/brand_images/)

## Prompt de génération

```text
Use case: logo-brand
Asset type: square application icon for Halo, a Home Assistant integration for whole-home lighting.
Primary request: a refined, simple lotus flower symbol. Symmetrical lotus with five bold, clean petals; the central petal evokes a gentle flame of light. Modern flat icon, crisp solid shapes, subtle warmth, elegant silhouette readable at 32 pixels. No thin decorative details.
Composition: only the lotus mark, centered, filling most of a square canvas with small balanced margins.
Scene/backdrop: fully transparent background with genuine alpha, no background plate, no scenery.
Constraints: no text, no letters, no watermark, no Home Assistant house logo, no shadows or mockup. The final artwork is an icon, not a presentation board. Please provide a PNG file suitable as a source image for 256 and 512 pixel application icons.
```

Paramètre : `transparent_background=true`.
