"""Sensor platform for IBEX BG integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, time
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import IbexBGAPI
from .const import (
    CONF_UPDATE_DAYS,
    CONF_UPDATE_END_TIME,
    CONF_UPDATE_INTERVAL,
    CONF_UPDATE_START_TIME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UPDATE_DAYS,
    DEFAULT_UPDATE_END_TIME,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_UPDATE_START_TIME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up IBEX BG sensor based on a config entry."""
    # Get the shared API client from the integration data
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]

    coordinator = IbexBGDataUpdateCoordinator(hass, api, config_entry)

    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        [
            IbexAveragePriceSensor(coordinator),
            IbexHighestPriceSensor(coordinator),
            IbexLowestPriceSensor(coordinator),
            IbexCurrentPriceSensor(coordinator),
            IbexCurrentPercentageSensor(coordinator),
            IbexNextHourPriceSensor(coordinator),
            IbexTimeOfHighestPriceSensor(coordinator),
            IbexTimeOfLowestPriceSensor(coordinator),
        ]
    )


class IbexBGDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the IBEX BG API."""

    def __init__(self, hass: HomeAssistant, api: IbexBGAPI, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self.api = api
        self.config_entry = config_entry
        
        # Get configuration
        update_interval = config_entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=update_interval),
        )

    def _should_update(self) -> bool:
        """Check if we should update based on time and day constraints."""
        now = datetime.now()
        current_time = now.time()
        current_day = now.strftime("%A").lower()
        
        # Get configuration
        start_time_str = self.config_entry.data.get(CONF_UPDATE_START_TIME, DEFAULT_UPDATE_START_TIME)
        end_time_str = self.config_entry.data.get(CONF_UPDATE_END_TIME, DEFAULT_UPDATE_END_TIME)
        update_days = self.config_entry.data.get(CONF_UPDATE_DAYS, DEFAULT_UPDATE_DAYS)
        
        # Parse time strings
        try:
            start_time = datetime.strptime(start_time_str, "%H:%M").time()
            end_time = datetime.strptime(end_time_str, "%H:%M").time()
        except ValueError:
            _LOGGER.warning("Invalid time format in configuration, using defaults")
            start_time = datetime.strptime(DEFAULT_UPDATE_START_TIME, "%H:%M").time()
            end_time = datetime.strptime(DEFAULT_UPDATE_END_TIME, "%H:%M").time()
        
        # Check if current day is in update days
        if current_day not in update_days:
            return False
        
        # Check if current time is within the update window
        if start_time <= end_time:
            # Normal case: start_time <= end_time (e.g., 09:00 to 17:00)
            return start_time <= current_time <= end_time
        else:
            # Overnight case: start_time > end_time (e.g., 22:00 to 06:00)
            return current_time >= start_time or current_time <= end_time

    async def _async_update_data(self) -> dict:
        """Update data via library."""
        # Check if we should update based on schedule
        if not self._should_update():
            _LOGGER.debug("Skipping update - outside configured time window")
            # Return existing data if available, otherwise return empty data
            if hasattr(self, 'data') and self.data:
                return self.data
            return {
                "prices": [],
                "current_price": None,
                "average_price": None,
                "min_price": None,
                "max_price": None,
                "total_volume": None,
            }
        
        try:
            data = await self.api.async_get_prices()
            if data is None:
                raise UpdateFailed("Failed to fetch IBEX BG prices")
            
            return {
                "prices": data,
                "current_price": self.api.get_current_price(data),
                "average_price": self.api.get_average_price(data),
                "min_price": self.api.get_min_price(data),
                "max_price": self.api.get_max_price(data),
                "total_volume": self.api.get_total_volume(data),
                "next_hour_price": self.api.get_next_hour_price(data),
                "current_percentage": self.api.get_current_percentage(data),
                "time_of_highest_price": self.api.get_time_of_highest_price(data),
                "time_of_lowest_price": self.api.get_time_of_lowest_price(data),
                "prices_attributes": self.api.get_prices_attributes(data),
            }
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")


class IbexBGSensor(CoordinatorEntity, SensorEntity):
    """Base class for IBEX BG sensors."""

    def __init__(self, coordinator: IbexBGDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "ibex_bg")},
            "name": "IBEX BG",
            "manufacturer": "IBEX",
            "model": "Day Ahead Market",
        }


class IbexAveragePriceSensor(IbexBGSensor):
    """Sensor for average IBEX price."""

    _attr_name = "Average Day-Ahead Electricity Price Today"
    _attr_unique_id = "ibex_average_price"
    _attr_native_unit_of_measurement = "BGN/MWh"
    _attr_icon = "mdi:chart-line"

    @property
    def native_value(self) -> float | None:
        """Return the average price."""
        return self.coordinator.data.get("average_price")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        return {
            "prices": self.coordinator.data.get("prices_attributes", []),
        }


class IbexHighestPriceSensor(IbexBGSensor):
    """Sensor for highest IBEX price."""

    _attr_name = "Highest Day-Ahead Electricity Price Today"
    _attr_unique_id = "ibex_highest_price"
    _attr_native_unit_of_measurement = "BGN/MWh"
    _attr_icon = "mdi:arrow-up"

    @property
    def native_value(self) -> float | None:
        """Return the highest price."""
        return self.coordinator.data.get("max_price")


class IbexLowestPriceSensor(IbexBGSensor):
    """Sensor for lowest IBEX price."""

    _attr_name = "Lowest Day-Ahead Electricity Price Today"
    _attr_unique_id = "ibex_lowest_price"
    _attr_native_unit_of_measurement = "BGN/MWh"
    _attr_icon = "mdi:arrow-down"

    @property
    def native_value(self) -> float | None:
        """Return the lowest price."""
        return self.coordinator.data.get("min_price")


class IbexCurrentPriceSensor(IbexBGSensor):
    """Sensor for current IBEX price."""

    _attr_name = "Current Day-Ahead Electricity Price"
    _attr_unique_id = "ibex_current_price"
    _attr_native_unit_of_measurement = "BGN/MWh"
    _attr_icon = "mdi:currency-usd"

    @property
    def native_value(self) -> float | None:
        """Return the current price."""
        return self.coordinator.data.get("current_price")


class IbexCurrentPercentageSensor(IbexBGSensor):
    """Sensor for current price percentage."""

    _attr_name = "Current Percentage Relative To Highest Electricity Price Of The Day"
    _attr_unique_id = "ibex_current_percentage"
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:percent"

    @property
    def native_value(self) -> float | None:
        """Return the current percentage."""
        return self.coordinator.data.get("current_percentage")


class IbexNextHourPriceSensor(IbexBGSensor):
    """Sensor for next hour IBEX price."""

    _attr_name = "Next Hour Day-Ahead Electricity Price"
    _attr_unique_id = "ibex_next_hour_price"
    _attr_native_unit_of_measurement = "BGN/MWh"
    _attr_icon = "mdi:clock-forward"

    @property
    def native_value(self) -> float | None:
        """Return the next hour price."""
        return self.coordinator.data.get("next_hour_price")


class IbexTimeOfHighestPriceSensor(IbexBGSensor):
    """Sensor for time of highest price."""

    _attr_name = "Time Of Highest Energy Price Today"
    _attr_unique_id = "ibex_time_of_highest_price"
    _attr_icon = "mdi:clock-time-four"

    @property
    def native_value(self) -> str | None:
        """Return the time of highest price."""
        return self.coordinator.data.get("time_of_highest_price")


class IbexTimeOfLowestPriceSensor(IbexBGSensor):
    """Sensor for time of lowest price."""

    _attr_name = "Time Of Lowest Energy Price Today"
    _attr_unique_id = "ibex_time_of_lowest_price"
    _attr_icon = "mdi:clock-time-one"

    @property
    def native_value(self) -> str | None:
        """Return the time of lowest price."""
        return self.coordinator.data.get("time_of_lowest_price")
