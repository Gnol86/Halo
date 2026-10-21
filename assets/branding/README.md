# Halo lotus

Initial proposal: a warm-toned lotus with five petals, with a central petal resembling a flame. The image was generated on October 9, 2026 using the built-in `image_gen` tool, following the request for a lotus flower.

- `lotus-source.png`: the generated source, preserved unchanged.
- `../../custom_components/halo/brand/icon.png`: transparent PNG, 256 × 256.
- `../../custom_components/halo/brand/icon@2x.png`: transparent PNG, 512 × 512.

The exports are simple resizes of the source, produced with `sips`. The same colors are used in light and dark themes; their appearance in the Home Assistant interface still needs visual verification. The symbol also serves as the logo through Home Assistant's fallback mechanism.

[Icon dimensions](https://github.com/home-assistant/brands#image-specification) · [Local images for custom integrations](https://developers.home-assistant.io/docs/core/integration/brand_images/)

## Generation prompt

```text
Use case: logo-brand
Asset type: square application icon for Halo, a Home Assistant integration for whole-home lighting.
Primary request: a refined, simple lotus flower symbol. Symmetrical lotus with five bold, clean petals; the central petal evokes a gentle flame of light. Modern flat icon, crisp solid shapes, subtle warmth, elegant silhouette readable at 32 pixels. No thin decorative details.
Composition: only the lotus mark, centered, filling most of a square canvas with small balanced margins.
Scene/backdrop: fully transparent background with genuine alpha, no background plate, no scenery.
Constraints: no text, no letters, no watermark, no Home Assistant house logo, no shadows or mockup. The final artwork is an icon, not a presentation board. Please provide a PNG file suitable as a source image for 256 and 512 pixel application icons.
```

Parameter: `transparent_background=true`.
