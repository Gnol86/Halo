<p align="center">
  <img src="https://raw.githubusercontent.com/Gnol86/Halo/main/custom_components/halo/brand/icon@2x.png" alt="Halo lotus" width="144" height="144">
</p>

# Halo - Home Assistant Light Orchestrator

[![Latest release](https://img.shields.io/github/v/release/Gnol86/Halo?label=release&style=flat-square)](https://github.com/Gnol86/Halo/releases/latest)
[![HACS default catalog](https://img.shields.io/badge/HACS-Default-41BDF5?logo=homeassistant&logoColor=white&style=flat-square)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Gnol86&repository=Halo&category=integration)
[![Community topic posts](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fcommunity.home-assistant.io%2Ft%2F1028198.json&query=%24.posts_count&label=community%20posts&logo=discourse&color=41BDF5&style=flat-square)](https://community.home-assistant.io/t/halo-home-assistant-light-orchestrator-presence-natural-light-and-scenes/1028198)
[![Total GitHub release asset downloads](https://img.shields.io/github/downloads/Gnol86/Halo/total?label=downloads&style=flat-square)](https://github.com/Gnol86/Halo/releases)
[![GitHub stars](https://img.shields.io/github/stars/Gnol86/Halo?style=flat-square&logo=github)](https://github.com/Gnol86/Halo)

<sub>The download badge counts GitHub release assets only. It does not measure source archive downloads or HACS installations.</sub>

**Lighting that follows your home, room by room.**

Halo is a custom Home Assistant integration that brings presence, ambient light, natural lighting profiles and scenes together in one place. Configure your rooms from a dedicated sidebar panel, let Halo handle everyday lighting, and take control whenever you need to.

**English** · [Français](docs/README.fr.md) · [Releases](https://github.com/Gnol86/Halo/releases) · [Community discussion](https://community.home-assistant.io/t/halo-home-assistant-light-orchestrator-presence-natural-light-and-scenes/1028198) · [Report an issue](https://github.com/Gnol86/Halo/issues)

One integration covers your home. The panel is included, follows your Home Assistant theme and works on desktop and mobile. No YAML or separate dashboard card is required to configure Halo. Its lighting engine runs inside Home Assistant and keeps working when the panel is closed.

<a href="https://raw.githubusercontent.com/Gnol86/Halo/main/docs/images/room-control-en.png">
  <img src="https://raw.githubusercontent.com/Gnol86/Halo/main/docs/images/room-control-en.png" alt="Simulated Halo room controls: eight areas, six configured rooms, natural lighting in the living room, and three Halo scenes" width="1000">
</a>

*Control every room from one panel. See which rooms use a scene, natural light, direct control or a nightlight, and launch an ambience with one click.*

## What Halo can do

| Feature | What it brings to your home |
| --- | --- |
| **Room automation** | Turn lights on with presence and off after a configurable absence delay. Use ambient-light thresholds and hysteresis to decide when lighting is needed. |
| **Lighting without an illuminance sensor** | Allow lighting at any time, within a daily time range, or below a chosen sun elevation. Time ranges can span midnight. |
| **Natural light profiles** | Adjust brightness and white temperature with the sun's elevation. Reuse profiles across rooms, set separate morning and evening curves, and fine-tune brightness for different groups of lights. |
| **Scenes and priorities** | Create room scenes with conditions based on entity states, numeric values, time or the sun. Order scenes by priority and choose whether each may turn the lights on automatically. |
| **Home Assistant scenes** | Link an existing scene to run it directly, or import an independent copy of its settings for the lights in your room when the source configuration is accessible. |
| **Nightlights** | Keep selected lights at fixed settings during confirmed absence, while turning the other room lights off. Nightlights follow the room's lighting permission. |
| **Direct control** | Turn lights on or off and launch scenes without suspending room automation. Turn **Automation** off when you want to keep control. |
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

Open Halo directly in HACS:

[![Open Halo in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Gnol86&repository=Halo&category=integration)

1. Open **HACS** in Home Assistant.
2. Search for **Halo**, open its entry, and download it.
3. Restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration**, search for **Halo**, and confirm setup.
5. Open **Halo** in the sidebar.

After downloading Halo and restarting Home Assistant, you can also open its setup wizard directly:

[![Add the Halo integration to Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=halo)

On first use, My Home Assistant may ask for the URL of your Home Assistant instance.

Add Halo once: the same integration manages every configured room.

#### If Halo does not appear in HACS

The catalog inclusion was merged on October 21, 2026. HACS [advises allowing up to 8 hours](https://github.com/hacs/default/pull/11771#issuecomment-6316138368) for newly accepted repositories to appear. If Halo is not listed in your instance, you can use a custom repository as a fallback:

1. In HACS, open the three-dot menu and select **Custom repositories**.
2. Add `https://github.com/Gnol86/Halo` with the type **Integration**.
3. Search for **Halo** and continue with the download and setup steps above.

See the [official HACS custom repository guide](https://www.hacs.xyz/docs/faq/custom_repositories/) for help with this fallback.

### Manual installation

1. Download the source archive from a [published release](https://github.com/Gnol86/Halo/releases).
2. Copy its `custom_components/halo` folder into your Home Assistant configuration directory, so that `custom_components/halo/manifest.json` exists there.
3. Restart Home Assistant, then add **Halo** from **Settings → Devices & services → Add integration**.

The compiled panel and brand images are included in the release. No frontend build is needed for installation.

### Updating

Update Halo through HACS, or replace the `custom_components/halo` folder with the one from the chosen release. Restart Home Assistant and reload your browser to load the updated panel. Read the [release notes](https://github.com/Gnol86/Halo/releases) for changes and compatibility information.

## Set up your first room

**Starting with 0.2.1:** a fresh installation creates a reusable **Natural light** profile automatically. In 0.4.0b2, new profiles use gradual curves (earlier releases used linear curves): brightness from **40% at −20°** to **100% at 20°**, and white temperature from **2,000 K at 0°** to **5,500 K at 20°**, with morning and evening linked. You can rename, adjust or delete it in **Natural light profiles**, then assign it to lights in each room's **Ambiences** tab. Existing installations keep their profiles, including an empty list; a deleted profile does not return after a restart.

1. Open **Halo → Rooms** and select a Home Assistant area.
2. In **Lights**, choose the lights Halo may control. Each light belongs to one Halo room; newly discovered lights are never added automatically.
3. In **Automation**, select your presence source and absence delay. Add an illuminance sensor and thresholds, or choose **Always**, **Time range** or **Sun elevation** when no sensor is configured.
4. Select **Save changes** to save the room. Automation starts disabled for newly configured rooms.
5. In **Ambiences**, optionally configure a base ambience, assign natural light profiles, or set up nightlights. Adjust or create reusable profiles in **Natural light profiles** and select the sun entity in **Global settings**. Save pending changes before opening the nightlight editor, then enable the nightlight after configuring its lights.
6. Save any remaining changes, then enable the room's **Automation** switch when ready.

Use **Control** to create or launch scenes, and **Settings** to customize room transitions. Changes remain in a shared draft as you move between tabs, rooms and profiles, until you save or discard them.

Each configured room also exposes Home Assistant entities: a room light, a status sensor, automatic-lighting and natural-light switches, and its scenes. Use them in your own dashboards and automations.

## A closer look

### Presence and ambient light

Choose a presence source, allow time before switching off an empty room, and set the illuminance threshold and hysteresis. Live readings help you understand when Halo permits lighting.

<a href="https://raw.githubusercontent.com/Gnol86/Halo/main/docs/images/room-automation-en.png">
  <img src="https://raw.githubusercontent.com/Gnol86/Halo/main/docs/images/room-automation-en.png" alt="Simulated living room automation settings with a presence sensor, a zero-second absence delay, a 50-lux turn-on threshold and 20-lux hysteresis" width="1000">
</a>

### Natural light profiles

**[Beta 0.4.0b2 — visual profile editor](https://github.com/Gnol86/Halo/releases/tag/v0.4.0b2):** adjust a whole day on one chart, with a dashed sun path, a brightness curve and an opaque fill showing white temperature. Separate morning and evening settings connect smoothly through daytime and nighttime in both the preview and lighting engine.

Brightness and temperature sliders use whole percentages and kelvins, with color guides and a logarithmic temperature scale. Sun handles adjust to hundredths of a degree. New profiles use gradual curves; existing values and exact advanced settings are preserved without migration. The schematic preview has no clock times and sends no light commands.

**0.3.1 remains the latest stable release.** Beta testing is optional: to include prereleases in HACS update checks for Halo, enable its HACS prerelease switch entity if disabled, then turn it on. The [HACS switch documentation](https://www.hacs.dev/docs/use/entities/switch/) explains this setting.

Drag the brightness and temperature markers independently, select the start or end of morning or evening, then adjust the two value sliders. Morning and evening remain visible together: unlink them for separate settings, or link them again to use the morning settings for both. Exact values and linear or gradual progression remain available in **Advanced settings**. Changes use the usual shared draft, save and discard actions.

<a href="https://raw.githubusercontent.com/Gnol86/Halo/main/docs/images/natural-profiles-en.png">
  <img src="https://raw.githubusercontent.com/Gnol86/Halo/main/docs/images/natural-profiles-en.png" alt="Simulated natural profile editor showing one schematic day, a dashed sun path, a brightness curve filled with white-temperature colors, separate elevation handles and gradient-guided value sliders for the simulated Wake-up and evening profile, with morning and evening unlinked and smooth daytime and nighttime joins" width="1000">
</a>

*A simulated preview of the beta editor. The fill and slider gradients help compare light values; they do not reproduce the appearance of a particular lamp.*

## How the lighting rules work

**Everyday lighting.** When presence and lighting permission allow it, Halo applies the first eligible conditional scene. If none applies, it uses the room's base ambience and active natural profiles. A scene explicitly allowed to turn lights on can do so independently of presence and ambient light, while still respecting disabled automation and live editing.

**Your manual choices.** Manual light changes and explicitly launched scenes are one-shot commands. They never suspend room automation. Halo does not immediately cancel its own explicit command, but its next normal automatic action may replace that setting or scene. To keep control, turn **Automation** off for the room; explicit commands remain available. Live scene editing still temporarily suspends automation while you work.

**Upgrading to 0.3.0.** Manual pauses have been removed entirely, including their detection, timers, settings, Activity messages and **Resume automation** buttons. Previously saved pauses are cleared before the lighting engine starts. If room automation is enabled, its normal rules apply immediately after the new version loads. Existing presence protection, unavailable-device handling and live-editing safeguards remain in place.

Custom dashboards or automations using Halo's removed resume buttons must be updated; use the existing **Automation** switch to enable or disable automatic control. The `halo/command` action `resume` and the `pause_until` status field are no longer available. Old `manual_pause` and `allow_off_during_pause` configuration fields are discarded when loaded or saved. The status sensor keeps the machine value `manual` for compatibility, now displayed as **Direct control**; it does not indicate or create a pause.

**Activity attribution in 0.2.2.** Light activity records commands from **Halo** and their reason: presence, the scene's custom name, nightlight, natural light, manual control or automatic shutoff. Commands are recorded as requests, separately from the light's reported state. When the light provider preserves context, the native activity detail also identifies Halo and the reason as the origin. Adjustments and commands whose feedback loses context still have a request entry. Linked Home Assistant scenes record their activation on the scene and its known light targets; Halo does not invent the contents of opaque scenes.

Activity and Recorder must be enabled and their filters still apply. Messages use Home Assistant's configured server language (French and its variants, English otherwise), preserving custom scene names. This does not change each user's panel language or enrich older history. The global feed can show both the Halo origin event and the target's request entry. Attribution is tested with Home Assistant's native activity processor and recorder using simulated lights. A read-only MCP inspection on October 12, 2026 confirmed 0.2.2 loaded and Halo command entries in the household activity log; it did not include visual verification or full hardware validation.

**Nightlights.** After confirmed absence, enabled nightlights replace normal lighting when permitted. They turn off when the room's lighting permission closes, even if automatic shutoff for normal lighting is disabled.

**Linked and imported scenes.** A linked Home Assistant scene runs in full and may control devices outside the Halo room. Halo does not restore those outside devices when the scene ends. An imported copy only includes matching lights selected in the room and stays independent of later source changes. Scenes whose settings are not exposed, including some provider scenes, can be linked but cannot necessarily be imported.

**Unavailable data.** Missing sensor readings are never treated as zero or as confirmed absence. A configured illuminance sensor remains authoritative even when unavailable; Halo does not silently switch to time or sun rules. Natural adjustments also wait when the required sun data is unavailable.

## Contributing

Join the [Home Assistant community discussion](https://community.home-assistant.io/t/halo-home-assistant-light-orchestrator-presence-natural-light-and-scenes/1028198) to ask questions, share your setup and give feedback. The community badge counts all posts in that topic, including the opening post.

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

If Halo is useful to you, you can [support its development on Buy Me a Coffee](https://buymeacoffee.com/gnol86).

<a href="https://buymeacoffee.com/gnol86">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Support Halo on Buy Me a Coffee" height="50">
</a>

Halo is released under the [MIT License](LICENSE).
