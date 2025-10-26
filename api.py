"""API client for IBEX BG."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

import aiohttp

from .const import API_COOKIES, API_HEADERS, API_PARAMS, API_URL

_LOGGER = logging.getLogger(__name__)


class IbexBGAPI:
    """API client for IBEX BG."""

    def __init__(self) -> None:
        """Initialize the API client."""
        self._session: aiohttp.ClientSession | None = None

    async def async_get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def async_close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def async_get_prices(self) -> list[dict[str, Any]] | None:
        """Get current IBEX BG prices."""
        try:
            session = await self.async_get_session()
            
            async with session.get(
                API_URL,
                params=API_PARAMS,
                headers=API_HEADERS,
                cookies=API_COOKIES,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    _LOGGER.debug("Successfully fetched %d price records", len(data))
                    return data
                else:
                    _LOGGER.error("Failed to fetch data. HTTP Status: %s", response.status)
                    return None
                    
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout while fetching IBEX BG prices")
            return None
        except aiohttp.ClientError as err:
            _LOGGER.error("Client error while fetching IBEX BG prices: %s", err)
            return None
        except Exception as err:
            _LOGGER.error("Unexpected error while fetching IBEX BG prices: %s", err)
            return None

    def get_current_price(self, data: list[dict[str, Any]]) -> float | None:
        """Get the price for the current time period."""
        if not data:
            return None
        
        from datetime import datetime
        now = datetime.now()
        today = now.date()
        
        _LOGGER.debug("get_current_price called at %s (today: %s)", now.strftime("%Y-%m-%d %H:%M:%S"), today)
        
        # Sort data by time to find the correct price
        # Handle both 'date' and 'time' field names
        def get_date_key(record):
            return record.get("date", record.get("time", ""))
        
        sorted_data = sorted(data, key=get_date_key)
        _LOGGER.debug("Processing %d price records", len(sorted_data))
        
        # First, try to find a price for today
        current_price = None
        last_today_price = None
        last_today_time = None
        
        for record in sorted_data:
            try:
                # Parse the date from the record (handle both 'date' and 'time' fields)
                date_str = record.get("date", record.get("time", ""))
                if not date_str:
                    continue
                
                # Handle different date formats
                if "T" in date_str:
                    # ISO format with T
                    record_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                else:
                    # Simple format like '2025-10-10 00:00:00'
                    record_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                
                # Check if this record is for today
                if record_date.date() == today:
                    last_today_price = record.get("price")
                    last_today_time = record_date
                    _LOGGER.debug("Found today's record: %s -> price: %s", record_date.strftime("%H:%M:%S"), record.get("price"))
                    
                    # If current time is before this record's time, use the previous price
                    if now < record_date:
                        _LOGGER.debug("Current time %s is before record time %s, breaking", now.strftime("%H:%M:%S"), record_date.strftime("%H:%M:%S"))
                        break
                    
                    # If current time is at or after this record's time, use this price
                    current_price = record.get("price")
                    _LOGGER.debug("Current time %s is at/after record time %s, using price: %s", now.strftime("%H:%M:%S"), record_date.strftime("%H:%M:%S"), current_price)
                    
            except (ValueError, TypeError) as e:
                _LOGGER.debug("Error parsing date '%s': %s", date_str, e)
                continue
        
        # If we found a price for today, check if we're past the last today's price
        if current_price is not None and last_today_time is not None:
            if now > last_today_time:
                _LOGGER.debug("Past today's last price (%s), looking for tomorrow's first price", last_today_time.strftime("%H:%M:%S"))
                # We're past today's last price, look for tomorrow's first price
                for record in sorted_data:
                    try:
                        date_str = record.get("date", record.get("time", ""))
                        if not date_str:
                            continue
                        
                        if "T" in date_str:
                            record_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        else:
                            record_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        
                        # If this is tomorrow's data, use the first price
                        if record_date.date() > today:
                            _LOGGER.debug("Found tomorrow's first price: %s", record.get("price"))
                            return record.get("price")
                            
                    except (ValueError, TypeError):
                        continue
            else:
                _LOGGER.debug("Returning today's current price: %s", current_price)
                return current_price
        elif current_price is not None:
            _LOGGER.debug("Returning today's current price: %s", current_price)
            return current_price
        
        # If we have no prices for today at all, check if we only have tomorrow's prices
        # In this case, we should not return tomorrow's price as current price
        has_today_prices = any(
            self._is_today_record(record) for record in sorted_data
        )
        
        if not has_today_prices:
            _LOGGER.debug("No prices available for today, only future prices available")
            # Check if we have tomorrow's prices
            has_tomorrow_prices = any(
                self._is_tomorrow_record(record) for record in sorted_data
            )
            if has_tomorrow_prices:
                _LOGGER.debug("Only tomorrow's prices available, returning None for current price")
                return None
        
        # If no price found for today or tomorrow, return the most recent price overall
        fallback_price = sorted_data[-1].get("price") if sorted_data else None
        _LOGGER.debug("No current price found, returning fallback: %s", fallback_price)
        return fallback_price

    def get_average_price(self, data: list[dict[str, Any]]) -> float | None:
        """Calculate average price from the data."""
        if not data:
            return None
        
        prices = [record.get("price", 0) for record in data if record.get("price")]
        return sum(prices) / len(prices) if prices else None

    def get_min_price(self, data: list[dict[str, Any]]) -> float | None:
        """Get minimum price from the data."""
        if not data:
            return None
        
        prices = [record.get("price", 0) for record in data if record.get("price")]
        return min(prices) if prices else None

    def get_max_price(self, data: list[dict[str, Any]]) -> float | None:
        """Get maximum price from the data."""
        if not data:
            return None
        
        prices = [record.get("price", 0) for record in data if record.get("price")]
        return max(prices) if prices else None

    def get_total_volume(self, data: list[dict[str, Any]]) -> float | None:
        """Calculate total volume from the data."""
        if not data:
            return None
        
        volumes = [record.get("volume", 0) for record in data if record.get("volume")]
        return sum(volumes) if volumes else None

    def get_next_hour_price(self, data: list[dict[str, Any]]) -> float | None:
        """Get the price for the next hour."""
        if not data:
            return None
        
        from datetime import datetime, timedelta
        now = datetime.now()
        next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        
        # Find the price for the next hour
        for record in data:
            try:
                record_date = datetime.fromisoformat(record.get("date", "").replace("Z", "+00:00"))
                if record_date.hour == next_hour.hour and record_date.date() == next_hour.date():
                    return record.get("price")
            except (ValueError, TypeError):
                continue
        
        return None

    def get_current_percentage(self, data: list[dict[str, Any]]) -> float | None:
        """Get current price as percentage of highest price."""
        if not data:
            return None
        
        current_price = self.get_current_price(data)
        max_price = self.get_max_price(data)
        
        if current_price is None or max_price is None or max_price == 0:
            return None
        
        return (current_price / max_price) * 100

    def get_time_of_highest_price(self, data: list[dict[str, Any]]) -> str | None:
        """Get the time of the highest price."""
        if not data:
            return None
        
        max_price = self.get_max_price(data)
        if max_price is None:
            return None
        
        for record in data:
            if record.get("price") == max_price:
                return record.get("date")
        
        return None

    def get_time_of_lowest_price(self, data: list[dict[str, Any]]) -> str | None:
        """Get the time of the lowest price."""
        if not data:
            return None
        
        min_price = self.get_min_price(data)
        if min_price is None:
            return None
        
        for record in data:
            if record.get("price") == min_price:
                return record.get("date")
        
        return None

    def get_prices_attributes(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Get formatted prices for attributes (24h forecast)."""
        if not data:
            return []
        
        # Sort by date and format for attributes
        sorted_data = sorted(data, key=lambda x: x.get("date", ""))
        return [
            {
                "time": record.get("date"),
                "price": record.get("price", 0)
            }
            for record in sorted_data
        ]

    def get_next_price_change_time(self, data: list[dict[str, Any]]) -> datetime | None:
        """Get the next price change time from the data."""
        if not data:
            return None
        
        from datetime import datetime
        now = datetime.now()
        
        # Sort data by time
        def get_date_key(record):
            return record.get("date", record.get("time", ""))
        
        sorted_data = sorted(data, key=get_date_key)
        
        # Find the next price change after current time
        for record in sorted_data:
            try:
                date_str = record.get("date", record.get("time", ""))
                if not date_str:
                    continue
                
                # Handle different date formats
                if "T" in date_str:
                    record_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                else:
                    record_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                
                # If this record is in the future (after current time), return it
                if record_date > now:
                    return record_date
                    
            except (ValueError, TypeError):
                continue
        
        # No future price changes found
        return None

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

    def _is_tomorrow_record(self, record: dict) -> bool:
        """Check if a record is for tomorrow."""
        from datetime import datetime, timedelta
        try:
            date_str = record.get("date", record.get("time", ""))
            if not date_str:
                return False
            
            if "T" in date_str:
                record_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                record_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            
            tomorrow = datetime.now().date() + timedelta(days=1)
            return record_date.date() == tomorrow
        except (ValueError, TypeError):
            return False
