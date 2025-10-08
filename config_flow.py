"""Config flow for IBEX BG integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    AVAILABLE_DAYS,
    CONF_UPDATE_DAYS,
    CONF_UPDATE_END_TIME,
    CONF_UPDATE_INTERVAL,
    CONF_UPDATE_START_TIME,
    DEFAULT_UPDATE_DAYS,
    DEFAULT_UPDATE_END_TIME,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_UPDATE_START_TIME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    # Since the API doesn't require authentication, we just validate the connection
    from .api import IbexBGAPI
    
    api = IbexBGAPI()
    try:
        prices = await api.async_get_prices()
        if prices is None:
            raise CannotConnect("Failed to fetch prices from IBEX API")
        await api.async_close()
    except Exception as err:
        _LOGGER.error("Validation error: %s", err)
        raise CannotConnect(f"Failed to connect to IBEX API: {err}") from err

    # Generate a unique title for multiple instances
    instance_count = len([entry for entry in hass.config_entries.async_entries(DOMAIN)])
    title = f"IBEX BG" if instance_count == 0 else f"IBEX BG {instance_count + 1}"
    
    return {"title": title}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for IBEX BG."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        # Allow multiple instances - don't set unique_id to allow multiple configs
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_UPDATE_INTERVAL,
                            default=DEFAULT_UPDATE_INTERVAL
                        ): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
                        vol.Required(
                            CONF_UPDATE_START_TIME,
                            default=DEFAULT_UPDATE_START_TIME
                        ): str,
                        vol.Required(
                            CONF_UPDATE_END_TIME,
                            default=DEFAULT_UPDATE_END_TIME
                        ): str,
                        vol.Required(
                            CONF_UPDATE_DAYS,
                            default=DEFAULT_UPDATE_DAYS
                        ): vol.All(vol.Coerce(list), vol.Length(min=1), [vol.In(AVAILABLE_DAYS)]),
                    }
                ),
            )

        errors = {}

        # Validate time format
        try:
            from datetime import datetime
            datetime.strptime(user_input[CONF_UPDATE_START_TIME], "%H:%M")
            datetime.strptime(user_input[CONF_UPDATE_END_TIME], "%H:%M")
        except ValueError:
            errors["base"] = "invalid_time_format"

        # Validate days selection
        if not user_input.get(CONF_UPDATE_DAYS):
            errors["base"] = "no_days_selected"

        if not errors:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_UPDATE_INTERVAL,
                        default=user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
                    vol.Required(
                        CONF_UPDATE_START_TIME,
                        default=user_input.get(CONF_UPDATE_START_TIME, DEFAULT_UPDATE_START_TIME)
                    ): str,
                    vol.Required(
                        CONF_UPDATE_END_TIME,
                        default=user_input.get(CONF_UPDATE_END_TIME, DEFAULT_UPDATE_END_TIME)
                    ): str,
                    vol.Required(
                        CONF_UPDATE_DAYS,
                        default=user_input.get(CONF_UPDATE_DAYS, DEFAULT_UPDATE_DAYS)
                    ): vol.All(vol.Coerce(list), vol.Length(min=1), [vol.In(AVAILABLE_DAYS)]),
                }
            ),
            errors=errors,
        )
