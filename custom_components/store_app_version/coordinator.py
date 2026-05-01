"""Data update coordinator for Store App Version."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
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
    PLATFORM_LABELS,
    PLATFORM_PLAY_STORE,
)
from .play_store import PLAY_STORE_URL, parse_play_store_html

_LOGGER = logging.getLogger(__name__)

HTTP_TIMEOUT = aiohttp.ClientTimeout(total=30)

COUNTRY_TO_LANG: dict[str, str] = {
    "us": "en",
    "gb": "en",
    "ca": "en",
    "au": "en",
    "ie": "en",
    "nz": "en",
    "in": "en",
    "sg": "en",
    "za": "en",
    "cz": "cs",
    "sk": "sk",
    "de": "de",
    "at": "de",
    "ch": "de",
    "fr": "fr",
    "be": "fr",
    "lu": "fr",
    "es": "es",
    "mx": "es",
    "ar": "es",
    "co": "es",
    "cl": "es",
    "pe": "es",
    "it": "it",
    "nl": "nl",
    "pl": "pl",
    "ru": "ru",
    "by": "ru",
    "ua": "uk",
    "br": "pt",
    "pt": "pt",
    "jp": "ja",
    "kr": "ko",
    "cn": "zh",
    "tw": "zh",
    "hk": "zh",
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

PLAY_STORE_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _country_to_lang(country: str) -> str:
    return COUNTRY_TO_LANG.get(country.lower(), "en")


async def async_fetch_app_store(
    session: aiohttp.ClientSession, app_id: str, country: str
) -> dict[str, Any]:
    """Fetch + map a single app from the iTunes Lookup API.

    Raises ``UpdateFailed`` on any error so the same exception type
    works for both the coordinator and the config flow validation.
    """
    params: dict[str, str] = {"country": country}
    if app_id.isdigit():
        params["id"] = app_id
    else:
        params["bundleId"] = app_id
    try:
        async with session.get(ITUNES_LOOKUP_URL, params=params, timeout=HTTP_TIMEOUT) as resp:
            resp.raise_for_status()
            payload = await resp.json(content_type=None)
    except aiohttp.ClientError as err:
        raise UpdateFailed(f"App Store request failed: {err}") from err

    results = payload.get("results") or []
    if not results:
        raise UpdateFailed(f"App '{app_id}' not found in App Store ({country})")
    return parse_itunes_lookup_item(results[0])


async def async_fetch_play_store(
    session: aiohttp.ClientSession, app_id: str, country: str
) -> dict[str, Any]:
    """Fetch + parse a single app from Google Play.

    Raises ``UpdateFailed`` on any error.
    """
    lang = _country_to_lang(country)
    params = {"id": app_id, "hl": lang, "gl": country}
    headers = {
        "User-Agent": PLAY_STORE_USER_AGENT,
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
                raise UpdateFailed(f"App '{app_id}' not found in Google Play ({country})")
            resp.raise_for_status()
            html = await resp.text()
    except aiohttp.ClientError as err:
        raise UpdateFailed(f"Google Play request failed: {err}") from err

    parsed = parse_play_store_html(html, app_id)
    if parsed is None:
        raise UpdateFailed(f"Could not locate metadata for '{app_id}' in Google Play ({country})")
    return parsed


async def async_validate_app(hass: HomeAssistant, platform: str, app_id: str, country: str) -> None:
    """Verify an app exists in the configured store/country.

    Used by the config flow before creating the entry. Raises
    ``UpdateFailed`` on any failure.
    """
    session = async_get_clientsession(hass)
    if platform == PLATFORM_APP_STORE:
        await async_fetch_app_store(session, app_id, country)
    elif platform == PLATFORM_PLAY_STORE:
        await async_fetch_play_store(session, app_id, country)
    else:
        raise UpdateFailed(f"Unknown platform: {platform}")


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
            entry.options.get(CONF_COUNTRY, entry.data.get(CONF_COUNTRY, DEFAULT_COUNTRY))
            or DEFAULT_COUNTRY
        ).lower()
        self.last_successful_fetch: datetime | None = None
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.platform}_{self.app_id}_{self.country}",
            update_interval=update_interval,
        )

    @property
    def device_id(self) -> str:
        """Stable identifier for the per-app HA device."""
        return f"{self.platform}_{self.app_id}_{self.country}"

    def build_device_info(self) -> DeviceInfo:
        """Build the DeviceInfo for the per-app HA device."""
        data = self.data or {}
        app_name = data.get("name") or self.app_id
        platform_label = PLATFORM_LABELS.get(self.platform, self.platform)
        return DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            name=f"{app_name} ({platform_label})",
            manufacturer=data.get("developer") or platform_label,
            model=platform_label,
            configuration_url=data.get("url"),
            entry_type=None,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        session = async_get_clientsession(self.hass)
        if self.platform == PLATFORM_APP_STORE:
            data = await async_fetch_app_store(session, self.app_id, self.country)
        elif self.platform == PLATFORM_PLAY_STORE:
            data = await async_fetch_play_store(session, self.app_id, self.country)
        else:
            raise UpdateFailed(f"Unknown platform: {self.platform}")
        self.last_successful_fetch = dt_util.utcnow()
        return data
