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
        update_time_str = config_entry.data.get("update_time", DEFAULT_UPDATE_TIME)
        self.retry_attempts = config_entry.data.get("retry_attempts", DEFAULT_RETRY_ATTEMPTS)
        self.retry_interval = config_entry.data.get("retry_interval", DEFAULT_RETRY_INTERVAL)
        
        # Parse update time
        try:
            self.update_time = datetime.strptime(update_time_str, "%H:%M").time()
        except ValueError:
            _LOGGER.warning("Invalid time format in configuration, using default")
            self.update_time = datetime.strptime(DEFAULT_UPDATE_TIME, "%H:%M").time()
        
        # Set initial update interval - will be adjusted dynamically based on price changes
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=15),  # Initial interval, will be adjusted dynamically
        )

    def _should_fetch_today(self) -> bool:
        """Check if we should fetch data today based on configuration."""
        now = datetime.now()
        current_day = now.strftime("%A").lower()
        update_days = self.config_entry.data.get("update_days", DEFAULT_UPDATE_DAYS)
        
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

    def _merge_price_data(self, current_data: list[dict], new_data: list[dict]) -> list[dict]:
        """Merge new price data with current data, keeping current day's data until day ends."""
        from datetime import datetime
        now = datetime.now()
        today = now.date()
        
        # If no current data, return new data
        if not current_data:
            return new_data
        
        # If no new data, return current data
        if not new_data:
            return current_data
        
        # Get the date of the first record in new data
        try:
            first_new_record = new_data[0]
            date_str = first_new_record.get("date", first_new_record.get("time", ""))
            if not date_str:
                return current_data
            
            if "T" in date_str:
                new_data_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                new_data_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            
            # If new data is for tomorrow and it's still today, merge the data
            if new_data_date.date() > today:
                _LOGGER.info("New data is for tomorrow (%s), merging with current day's data", new_data_date.date())
                
                # Keep current day's data and add tomorrow's data
                merged_data = []
                
                # Add current day's data
                for record in current_data:
                    try:
                        record_date_str = record.get("date", record.get("time", ""))
                        if "T" in record_date_str:
                            record_date = datetime.fromisoformat(record_date_str.replace("Z", "+00:00"))
                        else:
                            record_date = datetime.strptime(record_date_str, "%Y-%m-%d %H:%M:%S")
                        
                        if record_date.date() == today:
                            merged_data.append(record)
                    except (ValueError, TypeError):
                        continue
                
                # Add tomorrow's data
                merged_data.extend(new_data)
                
                _LOGGER.info("Merged data: %d current day records + %d tomorrow records = %d total", 
                           len([r for r in current_data if self._is_today_record(r)]), 
                           len(new_data), 
                           len(merged_data))
                
                return merged_data
            
            # If new data is for today or past, replace current data
            return new_data
            
        except (ValueError, TypeError, KeyError):
            _LOGGER.warning("Could not parse date from new data, keeping current data")
            return current_data

    def _is_today_record(self, record: dict) -> bool:
        """Check if a record is for today."""
        from datetime import datetime
        try:
            date_str = record.get("date", record.get("time", ""))
            if not date_str:
                return False
            
            if "T" in date_str:
                record_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                record_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            
            return record_date.date() == datetime.now().date()
        except (ValueError, TypeError):
            return False

    def _cleanup_old_data(self, prices: list[dict]) -> list[dict]:
        """Clean up old data to prevent stacking. Keep only today's and tomorrow's data."""
        from datetime import datetime, timedelta
        now = datetime.now()
        today = now.date()
        tomorrow = today + timedelta(days=1)
        
        cleaned_prices = []
        for record in prices:
            try:
                date_str = record.get("date", record.get("time", ""))
                if not date_str:
                    continue
                
                if "T" in date_str:
                    record_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                else:
                    record_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                
                # Keep only today's and tomorrow's data
                if record_date.date() in [today, tomorrow]:
                    cleaned_prices.append(record)
                    
            except (ValueError, TypeError):
                continue
        
        return cleaned_prices

    def _calculate_optimal_update_interval(self, prices: list[dict]) -> timedelta:
        """Calculate optimal update interval based on price change frequency."""
        if not prices:
            return timedelta(minutes=15)  # Default fallback
        
        from datetime import datetime, timedelta
        now = datetime.now()
        
        # Sort prices by time
        def get_date_key(record):
            return record.get("date", record.get("time", ""))
        
        sorted_prices = sorted(prices, key=get_date_key)
        
        # Find the next few price changes to determine optimal interval
        next_changes = []
        for record in sorted_prices:
            try:
                date_str = record.get("date", record.get("time", ""))
                if not date_str:
                    continue
                
                if "T" in date_str:
                    record_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                else:
                    record_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                
                # If this record is in the future, add to next changes
                if record_date > now:
                    next_changes.append(record_date)
                    if len(next_changes) >= 3:  # Look at next 3 changes
                        break
                        
            except (ValueError, TypeError):
                continue
        
        if not next_changes:
            return timedelta(minutes=15)  # Default fallback
        
        # Calculate intervals between price changes
        intervals = []
        for i in range(len(next_changes) - 1):
            interval = next_changes[i + 1] - next_changes[i]
            intervals.append(interval.total_seconds())
        
        if intervals:
            # Use the minimum interval, but cap it between 1 minute and 30 minutes
            min_interval_seconds = min(intervals)
            optimal_seconds = max(60, min(min_interval_seconds, 1800))  # 1 min to 30 min
            return timedelta(seconds=optimal_seconds)
        
        return timedelta(minutes=15)  # Default fallback

    async def _async_update_data(self) -> dict:
        """Update data via library."""
        now = datetime.now()
        today = now.date()
        _LOGGER.info("Coordinator update triggered at %s", now.strftime("%Y-%m-%d %H:%M:%S"))
        
        # Get existing data
        existing_data = self._get_existing_data()
        if existing_data.get("prices"):
            # Clean up old data at midnight to prevent stacking
            cleaned_prices = self._cleanup_old_data(existing_data["prices"])
            if len(cleaned_prices) != len(existing_data["prices"]):
                _LOGGER.info("Cleaned up old data: %d -> %d records", len(existing_data["prices"]), len(cleaned_prices))
                existing_data["prices"] = cleaned_prices
        
        # Check if we should fetch new data today
        if not self._should_fetch_today():
            _LOGGER.debug("Not a configured update day - using existing data with recalculated current price")
            return existing_data
        
        # Check if we should fetch new data
        should_fetch_new_data = False
        
        # Fetch new data if:
        # 1. We have no existing data at all, OR
        # 2. We haven't fetched today yet, OR
        # 3. It's the configured update time, OR
        # 4. We're in retry mode
        if (not existing_data.get("prices") or
            self.last_fetch_date != today or 
            self._is_update_time() or 
            self._should_retry()):
            should_fetch_new_data = True
        
        if not should_fetch_new_data:
            _LOGGER.debug("Using existing data")
            return existing_data
        
        try:
            _LOGGER.info(f"Fetching IBEX BG prices (attempt {self.retry_count + 1}/{self.retry_attempts})")
            data = await self.api.async_get_prices()
            
            if data is None or not data:
                if self._should_retry():
                    self.retry_count += 1
                    _LOGGER.warning(f"No data received, will retry in {self.retry_interval} minutes (attempt {self.retry_count}/{self.retry_attempts})")
                    # Schedule retry - but don't make it too frequent
                    retry_interval = timedelta(minutes=max(self.retry_interval, 15))
                    self.update_interval = retry_interval
                    raise UpdateFailed("No data received, will retry")
                else:
                    _LOGGER.error("No data received after all retry attempts")
                    raise UpdateFailed("Failed to fetch IBEX BG prices after all retries")
            
            # Merge new data with existing data (keep current day until it ends)
            current_prices = existing_data.get("prices", [])
            merged_prices = self._merge_price_data(current_prices, data)
            
            # Success - reset retry count and update last fetch date
            self.retry_count = 0
            self.last_fetch_date = today
            
            # Calculate optimal update interval based on price change frequency
            optimal_interval = self._calculate_optimal_update_interval(merged_prices)
            self.update_interval = optimal_interval
            
            _LOGGER.info("Successfully fetched IBEX BG prices - merged data: %d records, optimal update interval: %s", 
                        len(merged_prices), optimal_interval)
            return {
                "prices": merged_prices,
                "average_price": self.api.get_average_price(merged_prices),
                "min_price": self.api.get_min_price(merged_prices),
                "max_price": self.api.get_max_price(merged_prices),
                "total_volume": self.api.get_total_volume(merged_prices),
                "time_of_highest_price": self.api.get_time_of_highest_price(merged_prices),
                "time_of_lowest_price": self.api.get_time_of_lowest_price(merged_prices),
                "prices_attributes": self.api.get_prices_attributes(merged_prices),
            }
        except UpdateFailed:
            raise
        except Exception as err:
            if self._should_retry():
                self.retry_count += 1
                _LOGGER.warning(f"Error fetching data, will retry in {self.retry_interval} minutes: {err}")
                retry_interval = timedelta(minutes=max(self.retry_interval, 15))
                self.update_interval = retry_interval
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
            "average_price": None,
            "min_price": None,
            "max_price": None,
            "total_volume": None,
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
        
        # Get instance name
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


class IbexCurrentTimeBasedSensor(IbexBGSensor):
    """Base class for current time-based sensors that read from prices list."""

    def __init__(self, coordinator: IbexBGDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._update_timer = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        # Schedule the first update
        self._schedule_next_update()

    async def async_will_remove_from_hass(self) -> None:
        """When entity is removed from Home Assistant."""
        if self._update_timer:
            self._update_timer()
            self._update_timer = None
        await super().async_will_remove_from_hass()

    def _schedule_next_update(self) -> None:
        """Schedule the next update at the next price change time."""
        from datetime import datetime, timedelta
        
        now = datetime.now()
        
        # Try to get the next price change time from available data
        next_price_change = self._get_next_price_change_time()
        
        if next_price_change:
            # Calculate delay to next price change
            delay = (next_price_change - now).total_seconds()
            
            # Only schedule if the next change is within a reasonable timeframe (next 24 hours)
            if 0 < delay <= 86400:  # 24 hours in seconds
                _LOGGER.info("Scheduling current price sensor update in %.1f seconds (at %s) - next price change", 
                            delay, next_price_change.strftime("%Y-%m-%d %H:%M:%S"))
                
                # Cancel existing timer if any
                if self._update_timer:
                    self._update_timer()
                
                # Schedule the update
                self._update_timer = self.hass.loop.call_later(
                    delay, 
                    self._force_update
                )
                return
        
        # Fallback to 15-minute intervals if no price data or next change is too far
        _LOGGER.debug("No price change time found or too far in future, using 15-minute fallback")
        
        # Calculate the next 15-minute interval
        minutes_since_hour = now.minute
        next_15_min = ((minutes_since_hour // 15) + 1) * 15
        
        if next_15_min >= 60:
            # Next hour
            next_update = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        else:
            # Same hour
            next_update = now.replace(minute=next_15_min, second=0, microsecond=0)
        
        # Calculate delay in seconds
        delay = (next_update - now).total_seconds()
        
        _LOGGER.info("Scheduling current price sensor update in %.1f seconds (at %s) - fallback interval", 
                    delay, next_update.strftime("%H:%M:%S"))
        
        # Cancel existing timer if any
        if self._update_timer:
            self._update_timer()
        
        # Schedule the update
        self._update_timer = self.hass.loop.call_later(
            delay, 
            self._force_update
        )

    def _get_next_price_change_time(self) -> datetime | None:
        """Get the next price change time from available price data."""
        if not self.coordinator.data or not self.coordinator.data.get("prices"):
            return None
        
        # Use the API method to get the next price change time
        next_change = self.coordinator.api.get_next_price_change_time(self.coordinator.data["prices"])
        if next_change:
            _LOGGER.debug("Next price change found at %s", next_change.strftime("%Y-%m-%d %H:%M:%S"))
        return next_change

    def _force_update(self) -> None:
        """Force the sensor to update its state."""
        _LOGGER.info("Forcing current price sensor update at scheduled time")
        
        # Force the sensor to update its state
        self.async_schedule_update_ha_state()
        
        # Schedule the next update
        self._schedule_next_update()


class IbexCurrentPriceSensor(IbexCurrentTimeBasedSensor):
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
        """Return the current price based on current time from prices list."""
        if not self.coordinator.data or not self.coordinator.data.get("prices"):
            _LOGGER.debug("No price data available for current price sensor")
            return None
        
        # Get current price directly from the prices list based on current time
        current_price = self.coordinator.api.get_current_price(self.coordinator.data["prices"])
        _LOGGER.debug("Current price sensor queried - returning: %s", current_price)
        return current_price


class IbexCurrentPercentageSensor(IbexCurrentTimeBasedSensor):
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
        """Return the current percentage based on current time from prices list."""
        if not self.coordinator.data or not self.coordinator.data.get("prices"):
            return None
        
        # Get current percentage directly from the prices list based on current time
        return self.coordinator.api.get_current_percentage(self.coordinator.data["prices"])


class IbexNextHourPriceSensor(IbexCurrentTimeBasedSensor):
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
        """Return the next hour price based on current time from prices list."""
        if not self.coordinator.data or not self.coordinator.data.get("prices"):
            return None
        
        # Get next hour price directly from the prices list based on current time
        return self.coordinator.api.get_next_hour_price(self.coordinator.data["prices"])


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
