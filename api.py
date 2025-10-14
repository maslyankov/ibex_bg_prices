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
        
        # Sort data by time to find the correct price
        # Handle both 'date' and 'time' field names
        def get_date_key(record):
            return record.get("date", record.get("time", ""))
        
        sorted_data = sorted(data, key=get_date_key)
        
        # First, try to find a price for today
        current_price = None
        last_today_price = None
        
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
                    
                    # If current time is before this record's time, use the previous price
                    if now < record_date:
                        break
                    
                    # If current time is at or after this record's time, use this price
                    current_price = record.get("price")
                    
            except (ValueError, TypeError):
                continue
        
        # If we found a price for today, return it
        if current_price is not None:
            return current_price
        
        # If we're past today's last price, look for tomorrow's first price
        if last_today_price is not None:
            # We have today's data but we're past the last price
            # Look for tomorrow's first price
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
                        return record.get("price")
                        
                except (ValueError, TypeError):
                    continue
        
        # If no price found for today or tomorrow, return the most recent price overall
        return sorted_data[-1].get("price") if sorted_data else None

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
