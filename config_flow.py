"""Config flow for IBEX BG integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    AVAILABLE_DAYS,
    CONF_NAME,
    CONF_UPDATE_DAYS,
    CONF_UPDATE_TIME,
    CONF_RETRY_ATTEMPTS,
    CONF_RETRY_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_UPDATE_DAYS,
    DEFAULT_UPDATE_TIME,
    DEFAULT_RETRY_ATTEMPTS,
    DEFAULT_RETRY_INTERVAL,
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

    # Use the configured name or generate a unique title for multiple instances
    instance_name = data.get(CONF_NAME, DEFAULT_NAME).strip()
    
    if not instance_name:
        instance_name = DEFAULT_NAME
    
    # Check if this name is already used
    existing_entries = hass.config_entries.async_entries(DOMAIN)
    title = instance_name
    
    # If the name is already used, append a number
    if any(entry.title == title for entry in existing_entries):
        number = 2
        while any(entry.title == f"{title} {number}" for entry in existing_entries):
            number += 1
        title = f"{title} {number}"
    
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
                                CONF_NAME,
                                default=DEFAULT_NAME,
                                description="Friendly name for this IBEX BG integration instance"
                            ): str,
                            vol.Required(
                                CONF_UPDATE_TIME,
                                default=DEFAULT_UPDATE_TIME,
                                description="Time to fetch prices (24-hour format, e.g., 14:00 for 2 PM)"
                            ): str,
                            vol.Required(
                                CONF_UPDATE_DAYS,
                                default="monday,tuesday,wednesday,thursday,friday,saturday,sunday",
                                description="Days to fetch prices (comma-separated: monday,tuesday,wednesday,thursday,friday,saturday,sunday)"
                            ): str,
                            vol.Required(
                                CONF_RETRY_ATTEMPTS,
                                default=DEFAULT_RETRY_ATTEMPTS,
                                description="Number of retry attempts if no data is received"
                            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                            vol.Required(
                                CONF_RETRY_INTERVAL,
                                default=DEFAULT_RETRY_INTERVAL,
                                description="Minutes to wait between retry attempts"
                            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=120)),
                        }
                    ),
                )

        errors = {}

        # Validate instance name
        instance_name = user_input.get(CONF_NAME, "").strip()
        if not instance_name:
            errors["base"] = "name_required"
        elif len(instance_name) > 50:
            errors["base"] = "name_too_long"

        # Validate time format
        try:
            from datetime import datetime
            datetime.strptime(user_input[CONF_UPDATE_TIME], "%H:%M")
        except ValueError:
            errors["base"] = "invalid_time_format"

        # Validate days selection
        days_str = user_input.get(CONF_UPDATE_DAYS, "")
        if not days_str:
            errors["base"] = "no_days_selected"
        else:
            # Convert comma-separated string to list
            days = [day.strip() for day in days_str.split(",") if day.strip()]
            if not days:
                errors["base"] = "no_days_selected"
            elif not all(day in AVAILABLE_DAYS for day in days):
                errors["base"] = "invalid_days_selected"
            else:
                # Convert back to list for storage
                user_input[CONF_UPDATE_DAYS] = days

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
                        CONF_NAME,
                        default=user_input.get(CONF_NAME, DEFAULT_NAME),
                        description="Friendly name for this IBEX BG integration instance"
                    ): str,
                    vol.Required(
                        CONF_UPDATE_TIME,
                        default=user_input.get(CONF_UPDATE_TIME, DEFAULT_UPDATE_TIME),
                        description="Time to fetch prices (24-hour format, e.g., 14:00 for 2 PM)"
                    ): str,
                    vol.Required(
                        CONF_UPDATE_DAYS,
                        default=user_input.get(CONF_UPDATE_DAYS, "monday,tuesday,wednesday,thursday,friday,saturday,sunday"),
                        description="Days to fetch prices (comma-separated: monday,tuesday,wednesday,thursday,friday,saturday,sunday)"
                    ): str,
                    vol.Required(
                        CONF_RETRY_ATTEMPTS,
                        default=user_input.get(CONF_RETRY_ATTEMPTS, DEFAULT_RETRY_ATTEMPTS),
                        description="Number of retry attempts if no data is received"
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                    vol.Required(
                        CONF_RETRY_INTERVAL,
                        default=user_input.get(CONF_RETRY_INTERVAL, DEFAULT_RETRY_INTERVAL),
                        description="Minutes to wait between retry attempts"
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=120)),
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user(import_data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for IBEX BG."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME,
                        default=self.config_entry.data.get(CONF_NAME, DEFAULT_NAME),
                        description="Friendly name for this IBEX BG integration instance"
                    ): str,
                    vol.Required(
                        CONF_UPDATE_TIME,
                        default=self.config_entry.data.get(CONF_UPDATE_TIME, DEFAULT_UPDATE_TIME),
                        description="Time to fetch prices (24-hour format, e.g., 14:00 for 2 PM)"
                    ): str,
                    vol.Required(
                        CONF_UPDATE_DAYS,
                        default=self.config_entry.data.get(CONF_UPDATE_DAYS, "monday,tuesday,wednesday,thursday,friday,saturday,sunday"),
                        description="Days to fetch prices (comma-separated: monday,tuesday,wednesday,thursday,friday,saturday,sunday)"
                    ): str,
                    vol.Required(
                        CONF_RETRY_ATTEMPTS,
                        default=self.config_entry.data.get(CONF_RETRY_ATTEMPTS, DEFAULT_RETRY_ATTEMPTS),
                        description="Number of retry attempts if no data is received"
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                    vol.Required(
                        CONF_RETRY_INTERVAL,
                        default=self.config_entry.data.get(CONF_RETRY_INTERVAL, DEFAULT_RETRY_INTERVAL),
                        description="Minutes to wait between retry attempts"
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=120)),
                }
            ),
        )
