"""Data update coordinator for Store App Version."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_APP_ID,
    CONF_COUNTRY,
    CONF_PLATFORM,
    DEFAULT_COUNTRY,
    DOMAIN,
    PLATFORM_APP_STORE,
    PLATFORM_PLAY_STORE,
)

_LOGGER = logging.getLogger(__name__)

ITUNES_LOOKUP_URL = "https://itunes.apple.com/lookup"
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
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.platform}_{self.app_id}_{self.country}",
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        if self.platform == PLATFORM_APP_STORE:
            return await self._fetch_app_store()
        if self.platform == PLATFORM_PLAY_STORE:
            return await self._fetch_play_store()
        raise UpdateFailed(f"Unknown platform: {self.platform}")

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

        item = results[0]
        return {
            "version": item.get("version"),
            "name": item.get("trackName"),
            "developer": item.get("artistName"),
            "released": item.get("currentVersionReleaseDate"),
            "release_notes": item.get("releaseNotes"),
            "min_os_version": item.get("minimumOsVersion"),
            "size_bytes": _to_int(item.get("fileSizeBytes")),
            "rating": item.get("averageUserRating"),
            "rating_count": item.get("userRatingCount"),
            "url": item.get("trackViewUrl"),
            "icon": item.get("artworkUrl512") or item.get("artworkUrl100"),
        }

    async def _fetch_play_store(self) -> dict[str, Any]:
        try:
            return await self.hass.async_add_executor_job(self._sync_fetch_play_store)
        except Exception as err:  # noqa: BLE001 - scraper raises various
            raise UpdateFailed(f"Google Play request failed: {err}") from err

    def _sync_fetch_play_store(self) -> dict[str, Any]:
        from google_play_scraper import app  # noqa: PLC0415

        lang = _country_to_lang(self.country)
        result = app(self.app_id, lang=lang, country=self.country)
        return {
            "version": result.get("version"),
            "name": result.get("title"),
            "developer": result.get("developer"),
            "released": result.get("updated"),
            "release_notes": result.get("recentChanges"),
            "min_os_version": (
                result.get("androidVersionText") or result.get("androidVersion")
            ),
            "size_bytes": None,
            "rating": result.get("score"),
            "rating_count": result.get("ratings"),
            "url": result.get("url"),
            "icon": result.get("icon"),
            "installs": result.get("installs"),
        }


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
