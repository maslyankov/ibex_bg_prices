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
        """Get the most recent price from the data."""
        if not data:
            return None
        
        # Sort by date to get the most recent
        sorted_data = sorted(data, key=lambda x: x.get("date", ""), reverse=True)
        return sorted_data[0].get("price")

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
