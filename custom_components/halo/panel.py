"""Register the locally bundled panel in the Home Assistant sidebar."""

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN, NAME


async def async_register_panel(hass: HomeAssistant) -> None:
    """Serve static assets once, even when the entry is reloaded."""
    data = hass.data.setdefault(DOMAIN, {})
    if not data.get("static_registered"):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    "/halo_frontend", str(Path(__file__).parent / "frontend"), False
                )
            ]
        )
        data["static_registered"] = True
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=DOMAIN,
        webcomponent_name="halo-panel",
        sidebar_title=NAME,
        sidebar_icon="mdi:flower-lotus",
        module_url="/halo_frontend/halo-panel.js",
        require_admin=False,
        config_panel_domain=DOMAIN,
    )


def async_remove_panel(hass: HomeAssistant) -> None:
    """Remove the sidebar entry without disturbing other integrations."""
    frontend.async_remove_panel(hass, DOMAIN)
