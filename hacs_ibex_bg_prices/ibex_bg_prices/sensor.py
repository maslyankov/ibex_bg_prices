"""Sensor platform for IBEX BG integration."""
from __future__ import annotations

import logging
from datetime import timedelta

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
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up IBEX BG sensor based on a config entry."""
    api = IbexBGAPI()

    coordinator = IbexBGDataUpdateCoordinator(hass, api)

    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        [
            IbexCurrentPriceSensor(coordinator),
            IbexAveragePriceSensor(coordinator),
            IbexMinPriceSensor(coordinator),
            IbexMaxPriceSensor(coordinator),
            IbexTotalVolumeSensor(coordinator),
        ]
    )


class IbexBGDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the IBEX BG API."""

    def __init__(self, hass: HomeAssistant, api: IbexBGAPI) -> None:
        """Initialize."""
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict:
        """Update data via library."""
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


class IbexCurrentPriceSensor(IbexBGSensor):
    """Sensor for current IBEX price."""

    _attr_name = "IBEX Current Price"
    _attr_unique_id = "ibex_current_price"
    _attr_native_unit_of_measurement = "BGN/MWh"
    _attr_icon = "mdi:currency-usd"

    @property
    def native_value(self) -> float | None:
        """Return the current price."""
        return self.coordinator.data.get("current_price")


class IbexAveragePriceSensor(IbexBGSensor):
    """Sensor for average IBEX price."""

    _attr_name = "IBEX Average Price"
    _attr_unique_id = "ibex_average_price"
    _attr_native_unit_of_measurement = "BGN/MWh"
    _attr_icon = "mdi:chart-line"

    @property
    def native_value(self) -> float | None:
        """Return the average price."""
        return self.coordinator.data.get("average_price")


class IbexMinPriceSensor(IbexBGSensor):
    """Sensor for minimum IBEX price."""

    _attr_name = "IBEX Min Price"
    _attr_unique_id = "ibex_min_price"
    _attr_native_unit_of_measurement = "BGN/MWh"
    _attr_icon = "mdi:arrow-down"

    @property
    def native_value(self) -> float | None:
        """Return the minimum price."""
        return self.coordinator.data.get("min_price")


class IbexMaxPriceSensor(IbexBGSensor):
    """Sensor for maximum IBEX price."""

    _attr_name = "IBEX Max Price"
    _attr_unique_id = "ibex_max_price"
    _attr_native_unit_of_measurement = "BGN/MWh"
    _attr_icon = "mdi:arrow-up"

    @property
    def native_value(self) -> float | None:
        """Return the maximum price."""
        return self.coordinator.data.get("max_price")


class IbexTotalVolumeSensor(IbexBGSensor):
    """Sensor for total IBEX volume."""

    _attr_name = "IBEX Total Volume"
    _attr_unique_id = "ibex_total_volume"
    _attr_native_unit_of_measurement = "MWh"
    _attr_icon = "mdi:chart-bar"

    @property
    def native_value(self) -> float | None:
        """Return the total volume."""
        return self.coordinator.data.get("total_volume")
