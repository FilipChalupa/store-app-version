"""Data update coordinator for Store App Version."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .app_store import ITUNES_LOOKUP_URL, parse_itunes_lookup_item
from .const import (
    CONF_APP_ID,
    CONF_COUNTRY,
    CONF_PLATFORM,
    DEFAULT_COUNTRY,
    DOMAIN,
    PLATFORM_APP_STORE,
    PLATFORM_PLAY_STORE,
)
from .play_store import PLAY_STORE_URL, parse_play_store_html

_LOGGER = logging.getLogger(__name__)

HTTP_TIMEOUT = aiohttp.ClientTimeout(total=30)

COUNTRY_TO_LANG: dict[str, str] = {
    "us": "en", "gb": "en", "ca": "en", "au": "en", "ie": "en", "nz": "en",
    "in": "en", "sg": "en", "za": "en",
    "cz": "cs", "sk": "sk",
    "de": "de", "at": "de", "ch": "de",
    "fr": "fr", "be": "fr", "lu": "fr",
    "es": "es", "mx": "es", "ar": "es", "co": "es", "cl": "es", "pe": "es",
    "it": "it",
    "nl": "nl",
    "pl": "pl",
    "ru": "ru", "by": "ru",
    "ua": "uk",
    "br": "pt", "pt": "pt",
    "jp": "ja",
    "kr": "ko",
    "cn": "zh", "tw": "zh", "hk": "zh",
    "tr": "tr",
    "se": "sv",
    "no": "no",
    "dk": "da",
    "fi": "fi",
    "hu": "hu",
    "ro": "ro",
    "bg": "bg",
    "gr": "el",
    "il": "he",
    "id": "id",
    "th": "th",
    "vn": "vi",
}


def _country_to_lang(country: str) -> str:
    return COUNTRY_TO_LANG.get(country.lower(), "en")


class StoreAppVersionCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch app metadata from the configured store."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        update_interval: timedelta,
    ) -> None:
        self.entry = entry
        self.platform: str = entry.data[CONF_PLATFORM]
        self.app_id: str = entry.data[CONF_APP_ID]
        self.country: str = (
            entry.options.get(
                CONF_COUNTRY, entry.data.get(CONF_COUNTRY, DEFAULT_COUNTRY)
            )
            or DEFAULT_COUNTRY
        ).lower()
        self.last_successful_fetch: datetime | None = None
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.platform}_{self.app_id}_{self.country}",
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        if self.platform == PLATFORM_APP_STORE:
            data = await self._fetch_app_store()
        elif self.platform == PLATFORM_PLAY_STORE:
            data = await self._fetch_play_store()
        else:
            raise UpdateFailed(f"Unknown platform: {self.platform}")
        self.last_successful_fetch = dt_util.utcnow()
        return data

    async def _fetch_app_store(self) -> dict[str, Any]:
        session = async_get_clientsession(self.hass)
        params: dict[str, str] = {"country": self.country}
        if self.app_id.isdigit():
            params["id"] = self.app_id
        else:
            params["bundleId"] = self.app_id
        try:
            async with session.get(
                ITUNES_LOOKUP_URL, params=params, timeout=HTTP_TIMEOUT
            ) as resp:
                resp.raise_for_status()
                payload = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"App Store request failed: {err}") from err

        results = payload.get("results") or []
        if not results:
            raise UpdateFailed(
                f"App '{self.app_id}' not found in App Store ({self.country})"
            )

        return parse_itunes_lookup_item(results[0])

    async def _fetch_play_store(self) -> dict[str, Any]:
        session = async_get_clientsession(self.hass)
        lang = _country_to_lang(self.country)
        params = {"id": self.app_id, "hl": lang, "gl": self.country}
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": f"{lang},en;q=0.5",
        }
        try:
            async with session.get(
                PLAY_STORE_URL,
                params=params,
                timeout=HTTP_TIMEOUT,
                headers=headers,
            ) as resp:
                if resp.status == 404:
                    raise UpdateFailed(
                        f"App '{self.app_id}' not found in Google Play "
                        f"({self.country})"
                    )
                resp.raise_for_status()
                html = await resp.text()
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Google Play request failed: {err}") from err

        parsed = parse_play_store_html(html, self.app_id)
        if parsed is None:
            raise UpdateFailed(
                f"Could not locate metadata for '{self.app_id}' "
                f"in Google Play ({self.country})"
            )
        return parsed
