"""Describe dispatched commands without claiming their physical outcome."""

from collections.abc import Collection
from typing import Any

from homeassistant.const import EVENT_LOGBOOK_ENTRY
from homeassistant.core import Context, HomeAssistant, callback

from .const import EVENT_LIGHT_COMMAND, NAME

# Logbook messages are recorded server-side, in Home Assistant's configured
# language. Unlike panel strings, they cannot follow each viewer's locale.
_EN = {
    "turn_on": "turn-on requested",
    "turn_off": "turn-off requested",
    "adjust": "adjustment requested",
    "scene_action": "scene activation requested",
    "presence": "presence detected",
    "scene": "scene “{scene}”",
    "nightlight": "nightlight",
    "natural": "natural light",
    "base": "base ambience",
    "absence": "absence confirmed",
    "bright": "sufficient ambient light",
    "outside_schedule": "outside the lighting schedule",
    "sun_above_threshold": "sun above the lighting threshold",
    "lighting_allowed": "lighting now allowed",
    "refresh": "automatic lighting refreshed",
    "manual": "manual command in Halo",
    "preview": "live editing preview",
    "restore": "restoring lights after editing",
}
_FR = {
    "turn_on": "allumage demandé",
    "turn_off": "extinction demandée",
    "adjust": "ajustement demandé",
    "scene_action": "activation de scène demandée",
    "presence": "présence détectée",
    "scene": "scène « {scene} »",
    "nightlight": "veilleuse",
    "natural": "lumière naturelle",
    "base": "ambiance de base",
    "absence": "absence confirmée",
    "bright": "luminosité ambiante suffisante",
    "outside_schedule": "hors plage d'éclairage",
    "sun_above_threshold": "soleil au-dessus du seuil d'éclairage",
    "lighting_allowed": "éclairage à nouveau autorisé",
    "refresh": "éclairage automatique réévalué",
    "manual": "commande manuelle dans Halo",
    "preview": "aperçu pendant l'édition réelle",
    "restore": "restauration des lampes après édition",
}


@callback
def async_record_command(
    hass: HomeAssistant,
    context: Context,
    entity_id: str,
    action: str,
    reason: str,
    *,
    scene_name: str | None = None,
    related_lights: Collection[str] = (),
) -> None:
    """Record intent before dispatch, preserving the caller's context lineage."""
    language = hass.config.language.lower().replace("_", "-").split("-", 1)[0]
    texts = _FR if language == "fr" else _EN
    detail = texts[reason].format(scene=scene_name)
    data: dict[str, Any] = {
        "entity_id": entity_id,
        "name": f"{NAME} — {detail}",
        "message": f"{NAME} : {texts[action]} — {detail}",
        "reason": reason,
        "action": action,
    }
    if scene_name is not None:
        data["scene_name"] = scene_name
    # The first event on this context becomes its origin. The native logbook
    # platform describes it both for live feedback and recorded state changes.
    hass.bus.async_fire(EVENT_LIGHT_COMMAND, data, context=context)
    # Entity-filtered Activity only subscribes to the light provider's custom
    # events (Hue, ZHA, ...), not Halo's. A standard entry keeps the request in
    # that light's feed, including adjustments and contextless device feedback.
    for target in dict.fromkeys((entity_id, *sorted(related_lights))):
        hass.bus.async_fire(
            EVENT_LOGBOOK_ENTRY,
            {
                "name": NAME,
                "message": data["message"],
                "entity_id": target,
            },
            context=context,
        )
