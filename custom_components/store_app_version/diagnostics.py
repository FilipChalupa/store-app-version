"""Diagnostics for Store App Version.

Exposed in Home Assistant as a "Download diagnostics" button on the
integration entry. Dumps the config entry, the coordinator's last
fetched data, and the last update outcome — enough to debug "the
sensor is unknown / wrong" reports without asking users for logs.
"""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import StoreAppVersionCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: StoreAppVersionCoordinator | None = hass.data.get(DOMAIN, {}).get(
        entry.entry_id
    )

    diagnostics: dict[str, Any] = {
        "entry": {
            "title": entry.title,
            "unique_id": entry.unique_id,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
    }

    if coordinator is None:
        diagnostics["coordinator"] = None
        return diagnostics

    diagnostics["coordinator"] = {
        "platform": coordinator.platform,
        "app_id": coordinator.app_id,
        "country": coordinator.country,
        "update_interval_seconds": (
            coordinator.update_interval.total_seconds()
            if coordinator.update_interval
            else None
        ),
        "last_update_success": coordinator.last_update_success,
        "last_successful_fetch": (
            coordinator.last_successful_fetch.isoformat()
            if coordinator.last_successful_fetch
            else None
        ),
        "last_exception": (
            repr(coordinator.last_exception)
            if coordinator.last_exception
            else None
        ),
        "data": coordinator.data,
    }
    return diagnostics
