"""The IBEX BG integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import IbexBGAPI
from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up IBEX BG from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Create and store the API client
    api = IbexBGAPI()
    hass.data[DOMAIN][entry.entry_id] = {"api": api}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Close the API client session
        if entry.entry_id in hass.data[DOMAIN]:
            api = hass.data[DOMAIN][entry.entry_id].get("api")
            if api:
                await api.async_close()
            hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
