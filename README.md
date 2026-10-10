<p align="center">
  <img src="https://raw.githubusercontent.com/Gnol86/Halo/main/custom_components/halo/brand/icon@2x.png" alt="Halo lotus" width="144" height="144">
</p>

# Halo - Home Assistant Light Orchestrator

**Lighting that follows your home, room by room.**

Halo is a custom Home Assistant integration that brings presence, ambient light, natural lighting profiles and scenes together in one place. Configure your rooms from a dedicated sidebar panel, let Halo handle everyday lighting, and take control whenever you need to.

**English** · [Français](docs/README.fr.md) · [Releases](https://github.com/Gnol86/Halo/releases) · [Report an issue](https://github.com/Gnol86/Halo/issues)

One integration covers your home. The panel is included, follows your Home Assistant theme and works on desktop and mobile. No YAML or separate dashboard card is required to configure Halo. Its lighting engine runs inside Home Assistant and keeps working when the panel is closed.

> **Project status:** Halo is in early development, with published GitHub releases for installation through a HACS custom repository. Automated tests and targeted checks in an isolated Home Assistant instance use simulated lights; validation across real household hardware remains to be completed. The [default HACS catalog submission](https://github.com/hacs/default/pull/11771) is open and awaiting review; Halo is not yet listed.

## What Halo can do

| Feature | What it brings to your home |
| --- | --- |
| **Room automation** | Turn lights on with presence and off after a configurable absence delay. Use ambient-light thresholds and hysteresis to decide when lighting is needed. |
| **Lighting without an illuminance sensor** | Allow lighting at any time, within a daily time range, or below a chosen sun elevation. Time ranges can span midnight. |
| **Natural light profiles** | Adjust brightness and white temperature with the sun's elevation. Reuse profiles across rooms, set separate morning and evening curves, and fine-tune brightness for different groups of lights. |
| **Scenes and priorities** | Create room scenes with conditions based on entity states, numeric values, time or the sun. Order scenes by priority and choose whether each may turn the lights on automatically. |
| **Home Assistant scenes** | Link an existing scene to run it directly, or import an independent copy of its settings for the lights in your room when the source configuration is accessible. |
| **Nightlights** | Keep selected lights at fixed settings during confirmed absence, while turning the other room lights off. Nightlights follow the room's lighting permission. |
| **Manual control** | Manual changes pause automatic scene changes and natural adjustments for the whole room. Resume explicitly or let the configured pause rules take over. |
| **Transitions** | Set global transition durations for everyday lighting, natural adjustments, scenes and shutoff, with overrides for each room and support based on each light's capabilities. |

The panel includes searchable room and entity lists, live status, and scene editing through Home Assistant's native light controls. English and French are included: the panel follows each user's Home Assistant interface language, using French for its regional variants and English otherwise. Custom room, profile and scene names stay unchanged.

## Requirements

- **Home Assistant 2026.10.0 or newer.**
- Lights already available as Home Assistant `light` entities, and areas defined for the rooms you want to configure.
- An administrator account to install Halo and change its configuration. Other users can control rooms and launch scenes.
- A presence source for presence-based automation and nightlights. An illuminance sensor is optional; a sun entity is needed for natural profiles and sun-based lighting permission.
- HACS for the installation method below, or access to your Home Assistant configuration directory for manual installation.

Halo uses the capabilities exposed by your existing light integrations: on/off, dimming, white temperature, colors and effects where supported. Natural profiles require dimmable lights; color-only lights can approximate white temperature through their supported color mode.

## Installation

### With HACS

1. Open **HACS** in Home Assistant.
2. Open the three-dot menu and select **Custom repositories**.
3. Add `https://github.com/Gnol86/Halo` with the type **Integration**.
4. Find **Halo** in HACS and download it.
5. Restart Home Assistant.
6. Go to **Settings → Devices & services → Add integration**, search for **Halo**, and confirm setup.
7. Open **Halo** in the sidebar.

Add Halo once: the same integration manages every configured room. See the [official HACS custom repository guide](https://www.hacs.xyz/docs/faq/custom_repositories/) for help with adding the repository.

### Manual installation

1. Download the source archive from a [published release](https://github.com/Gnol86/Halo/releases).
2. Copy its `custom_components/halo` folder into your Home Assistant configuration directory, so that `custom_components/halo/manifest.json` exists there.
3. Restart Home Assistant, then add **Halo** from **Settings → Devices & services → Add integration**.

The compiled panel and brand images are included in the release. No frontend build is needed for installation.

### Updating

Update Halo through HACS, or replace the `custom_components/halo` folder with the one from the chosen release. Restart Home Assistant and reload your browser to load the updated panel. Read the [release notes](https://github.com/Gnol86/Halo/releases) for changes and compatibility information.

## Set up your first room

1. Open **Halo → Rooms** and select a Home Assistant area.
2. In **Lights**, choose the lights Halo may control. Each light belongs to one Halo room; newly discovered lights are never added automatically.
3. In **Automation**, select your presence source and absence delay. Add an illuminance sensor and thresholds, or choose **Always**, **Time range** or **Sun elevation** when no sensor is configured.
4. Select **Save changes** to save the room. Automation starts disabled for newly configured rooms.
5. In **Ambiences**, optionally configure a base ambience, assign natural light profiles, or set up nightlights. Create reusable profiles in **Natural light profiles** and select the sun entity in **Global settings**. Save pending changes before opening the nightlight editor, then enable the nightlight after configuring its lights.
6. Save any remaining changes, then enable the room's **Automation** switch when ready.

Use **Control** to create or launch scenes, and **Settings** to customize room transitions. Changes remain in a shared draft as you move between tabs, rooms and profiles, until you save or discard them.

Each configured room also exposes Home Assistant entities: a room light, a status sensor, automatic-lighting and natural-light switches, a resume button, and its scenes. Use them in your own dashboards and automations.

## How the lighting rules work

**Everyday lighting.** When presence and lighting permission allow it, Halo applies the first eligible conditional scene. If none applies, it uses the room's base ambience and active natural profiles. A scene explicitly allowed to turn lights on can do so independently of presence and ambient light, while still respecting manual pauses and disabled automation.

**Your manual choices.** Changing a light or explicitly launching a scene starts a room-wide pause. The pause ends when its timer expires, when you return after a sufficiently long confirmed absence, or when you select **Resume automation**. Automatic shutoff during a manual pause is configurable per room and enabled by default. Turning the entire room off manually blocks automatic relighting, including nightlights, for that pause.

**Nightlights.** After confirmed absence, enabled nightlights replace normal lighting when permitted. They turn off when the room's lighting permission closes, even if automatic shutoff for normal lighting is disabled.

**Linked and imported scenes.** A linked Home Assistant scene runs in full and may control devices outside the Halo room. Halo does not restore those outside devices when the scene ends. An imported copy only includes matching lights selected in the room and stays independent of later source changes. Scenes whose settings are not exposed, including some provider scenes, can be linked but cannot necessarily be imported.

**Unavailable data.** Missing sensor readings are never treated as zero or as confirmed absence. A configured illuminance sensor remains authoritative even when unavailable; Halo does not silently switch to time or sun rules. Natural adjustments also pause when the required sun data is unavailable.

## Contributing

Bug reports and contributions are welcome. When [opening an issue](https://github.com/Gnol86/Halo/issues), include your Halo and Home Assistant versions, the relevant light integration, steps to reproduce, and expected versus observed behavior.

Run Python checks from the repository root:

```sh
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
```

For panel changes, use Node.js 24 and run `npm ci`, `npm run check`, `npm test` and `npm run build` from the repository root. Include the rebuilt `custom_components/halo/frontend/halo-panel.js` with your changes. See the [panel README](frontend/README.md) for the simulated preview and panel behavior.

Automated tests and simulated previews do not validate hardware behavior, provider-specific effects or physical transitions on the target equipment.

## Support and license

If Halo is useful to you, you can [support its development on Buy Me a Coffee](https://www.buymeacoffee.com/gnol86).

Halo is released under the [MIT License](LICENSE).
