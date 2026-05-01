"""The Store App Version integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import (
    CONF_APP_ID,
    CONF_PLATFORM,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORM_LABELS,
)
from .coordinator import StoreAppVersionCoordinator

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.SENSOR]


def _issue_id(entry: ConfigEntry) -> str:
    return f"fetch_failed_{entry.entry_id}"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Store App Version from a config entry."""
    scan_interval_minutes = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )
    coordinator = StoreAppVersionCoordinator(
        hass,
        entry,
        update_interval=timedelta(minutes=scan_interval_minutes),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    entry.async_on_unload(
        coordinator.async_add_listener(_make_health_listener(hass, entry, coordinator))
    )
    return True


def _make_health_listener(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: StoreAppVersionCoordinator,
) -> callback:
    """Build a listener that surfaces a Repair issue while fetches fail."""
    issue_id = _issue_id(entry)
    platform_label = PLATFORM_LABELS.get(entry.data[CONF_PLATFORM], entry.data[CONF_PLATFORM])

    @callback
    def _on_update() -> None:
        if coordinator.last_update_success:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
            return
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="fetch_failed",
            translation_placeholders={
                "app_id": entry.data[CONF_APP_ID],
                "country": coordinator.country,
                "platform": platform_label,
                "error": (
                    str(coordinator.last_exception) if coordinator.last_exception else "unknown"
                ),
            },
        )

    return _on_update


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        ir.async_delete_issue(hass, DOMAIN, _issue_id(entry))
    return unloaded
