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
    CONF_NAME,
    CONF_UPDATE_DAYS,
    CONF_UPDATE_TIME,
    CONF_RETRY_ATTEMPTS,
    CONF_RETRY_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UPDATE_DAYS,
    DEFAULT_UPDATE_TIME,
    DEFAULT_RETRY_ATTEMPTS,
    DEFAULT_RETRY_INTERVAL,
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
        self.last_fetch_date = None
        self.retry_count = 0
        
        # Get configuration
        update_time_str = config_entry.data.get(CONF_UPDATE_TIME, DEFAULT_UPDATE_TIME)
        self.retry_attempts = config_entry.data.get(CONF_RETRY_ATTEMPTS, DEFAULT_RETRY_ATTEMPTS)
        self.retry_interval = config_entry.data.get(CONF_RETRY_INTERVAL, DEFAULT_RETRY_INTERVAL)
        
        # Parse update time
        try:
            self.update_time = datetime.strptime(update_time_str, "%H:%M").time()
        except ValueError:
            _LOGGER.warning("Invalid time format in configuration, using default")
            self.update_time = datetime.strptime(DEFAULT_UPDATE_TIME, "%H:%M").time()
        
        # Set a long update interval since we only fetch once per day
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=1),  # Check every hour if we should fetch
        )

    def _should_fetch_today(self) -> bool:
        """Check if we should fetch data today based on configuration."""
        now = datetime.now()
        current_day = now.strftime("%A").lower()
        update_days = self.config_entry.data.get(CONF_UPDATE_DAYS, DEFAULT_UPDATE_DAYS)
        
        # Check if current day is in update days
        return current_day in update_days

    def _is_update_time(self) -> bool:
        """Check if current time is the configured update time."""
        now = datetime.now()
        current_time = now.time()
        
        # Check if we're within 5 minutes of the update time
        time_diff = abs((datetime.combine(now.date(), current_time) - 
                        datetime.combine(now.date(), self.update_time)).total_seconds())
        return time_diff <= 300  # 5 minutes tolerance

    def _should_retry(self) -> bool:
        """Check if we should retry fetching data."""
        return self.retry_count < self.retry_attempts

    async def _async_update_data(self) -> dict:
        """Update data via library."""
        now = datetime.now()
        today = now.date()
        
        # Check if we should fetch today
        if not self._should_fetch_today():
            _LOGGER.debug("Skipping update - not a configured update day")
            return self._get_existing_data()
        
        # Always recalculate current price with existing data first
        existing_data = self._get_existing_data()
        if existing_data.get("prices"):
            _LOGGER.debug("Recalculating current price with existing data")
            existing_data["current_price"] = self.api.get_current_price(existing_data["prices"])
            existing_data["current_percentage"] = self.api.get_current_percentage(existing_data["prices"])
            existing_data["next_hour_price"] = self.api.get_next_hour_price(existing_data["prices"])
        
        # Check if we should fetch new data
        should_fetch_new_data = False
        
        # Fetch new data if:
        # 1. We haven't fetched today yet, OR
        # 2. It's the configured update time, OR
        # 3. We're in retry mode
        if (self.last_fetch_date != today or 
            self._is_update_time() or 
            self._should_retry()):
            should_fetch_new_data = True
        
        if not should_fetch_new_data:
            _LOGGER.debug("Using existing data with recalculated current price")
            return existing_data
        
        try:
            _LOGGER.info(f"Fetching IBEX BG prices (attempt {self.retry_count + 1}/{self.retry_attempts})")
            data = await self.api.async_get_prices()
            
            if data is None or not data:
                if self._should_retry():
                    self.retry_count += 1
                    _LOGGER.warning(f"No data received, will retry in {self.retry_interval} minutes (attempt {self.retry_count}/{self.retry_attempts})")
                    # Schedule retry
                    self.update_interval = timedelta(minutes=self.retry_interval)
                    raise UpdateFailed("No data received, will retry")
                else:
                    _LOGGER.error("No data received after all retry attempts")
                    raise UpdateFailed("Failed to fetch IBEX BG prices after all retries")
            
            # Success - reset retry count and update last fetch date
            self.retry_count = 0
            self.last_fetch_date = today
            self.update_interval = timedelta(hours=1)  # Back to hourly checks
            
            _LOGGER.info("Successfully fetched IBEX BG prices")
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
        except UpdateFailed:
            raise
        except Exception as err:
            if self._should_retry():
                self.retry_count += 1
                _LOGGER.warning(f"Error fetching data, will retry in {self.retry_interval} minutes: {err}")
                self.update_interval = timedelta(minutes=self.retry_interval)
                raise UpdateFailed(f"Error communicating with API, will retry: {err}")
            else:
                _LOGGER.error(f"Error communicating with API after all retries: {err}")
                raise UpdateFailed(f"Error communicating with API: {err}")

    def _get_existing_data(self) -> dict:
        """Return existing data if available, otherwise return empty data."""
        if hasattr(self, 'data') and self.data:
            return self.data
        return {
            "prices": [],
            "current_price": None,
            "average_price": None,
            "min_price": None,
            "max_price": None,
            "total_volume": None,
            "next_hour_price": None,
            "current_percentage": None,
            "time_of_highest_price": None,
            "time_of_lowest_price": None,
            "prices_attributes": [],
        }


class IbexBGSensor(CoordinatorEntity, SensorEntity):
    """Base class for IBEX BG sensors."""

    def __init__(self, coordinator: IbexBGDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        # Use config entry ID to make device and entity IDs unique per instance
        config_entry = coordinator.config_entry
        
        # Get instance name with fallback
        try:
            instance_name = config_entry.data.get(CONF_NAME, DEFAULT_NAME)
        except NameError:
            # Fallback if CONF_NAME is not available
            instance_name = config_entry.data.get("name", DEFAULT_NAME)
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": instance_name,
            "manufacturer": "IBEX",
            "model": "Day Ahead Market",
        }


class IbexAveragePriceSensor(IbexBGSensor):
    """Sensor for average IBEX price."""

    _attr_name = "Average Day-Ahead Electricity Price Today"
    _attr_native_unit_of_measurement = "BGN/MWh"
    _attr_icon = "mdi:chart-line"

    def __init__(self, coordinator: IbexBGDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"ibex_average_price_{coordinator.config_entry.entry_id}"

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
    _attr_native_unit_of_measurement = "BGN/MWh"
    _attr_icon = "mdi:arrow-up"

    def __init__(self, coordinator: IbexBGDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"ibex_highest_price_{coordinator.config_entry.entry_id}"

    @property
    def native_value(self) -> float | None:
        """Return the highest price."""
        return self.coordinator.data.get("max_price")


class IbexLowestPriceSensor(IbexBGSensor):
    """Sensor for lowest IBEX price."""

    _attr_name = "Lowest Day-Ahead Electricity Price Today"
    _attr_native_unit_of_measurement = "BGN/MWh"
    _attr_icon = "mdi:arrow-down"

    def __init__(self, coordinator: IbexBGDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"ibex_lowest_price_{coordinator.config_entry.entry_id}"

    @property
    def native_value(self) -> float | None:
        """Return the lowest price."""
        return self.coordinator.data.get("min_price")


class IbexCurrentPriceSensor(IbexBGSensor):
    """Sensor for current IBEX price."""

    _attr_name = "Current Day-Ahead Electricity Price"
    _attr_native_unit_of_measurement = "BGN/MWh"
    _attr_icon = "mdi:currency-usd"

    def __init__(self, coordinator: IbexBGDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"ibex_current_price_{coordinator.config_entry.entry_id}"

    @property
    def native_value(self) -> float | None:
        """Return the current price."""
        return self.coordinator.data.get("current_price")


class IbexCurrentPercentageSensor(IbexBGSensor):
    """Sensor for current price percentage."""

    _attr_name = "Current Percentage Relative To Highest Electricity Price Of The Day"
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:percent"

    def __init__(self, coordinator: IbexBGDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"ibex_current_percentage_{coordinator.config_entry.entry_id}"

    @property
    def native_value(self) -> float | None:
        """Return the current percentage."""
        return self.coordinator.data.get("current_percentage")


class IbexNextHourPriceSensor(IbexBGSensor):
    """Sensor for next hour IBEX price."""

    _attr_name = "Next Hour Day-Ahead Electricity Price"
    _attr_native_unit_of_measurement = "BGN/MWh"
    _attr_icon = "mdi:clock-forward"

    def __init__(self, coordinator: IbexBGDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"ibex_next_hour_price_{coordinator.config_entry.entry_id}"

    @property
    def native_value(self) -> float | None:
        """Return the next hour price."""
        return self.coordinator.data.get("next_hour_price")


class IbexTimeOfHighestPriceSensor(IbexBGSensor):
    """Sensor for time of highest price."""

    _attr_name = "Time Of Highest Energy Price Today"
    _attr_icon = "mdi:clock-time-four"

    def __init__(self, coordinator: IbexBGDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"ibex_time_of_highest_price_{coordinator.config_entry.entry_id}"

    @property
    def native_value(self) -> str | None:
        """Return the time of highest price."""
        return self.coordinator.data.get("time_of_highest_price")


class IbexTimeOfLowestPriceSensor(IbexBGSensor):
    """Sensor for time of lowest price."""

    _attr_name = "Time Of Lowest Energy Price Today"
    _attr_icon = "mdi:clock-time-one"

    def __init__(self, coordinator: IbexBGDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"ibex_time_of_lowest_price_{coordinator.config_entry.entry_id}"

    @property
    def native_value(self) -> str | None:
        """Return the time of lowest price."""
        return self.coordinator.data.get("time_of_lowest_price")
