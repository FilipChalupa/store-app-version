"""Button platform for Store App Version.

Provides a "Refresh now" button per app, disabled by default. Pressing
it requests an immediate refresh of the coordinator instead of waiting
for the next scheduled poll. Useful for testing, ad-hoc verification,
or wiring into automations.
"""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import StoreAppVersionCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: StoreAppVersionCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([StoreAppRefreshButton(coordinator)])


class StoreAppRefreshButton(ButtonEntity):
    """Button that triggers an immediate coordinator refresh."""

    _attr_has_entity_name = True
    _attr_translation_key = "refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: StoreAppVersionCoordinator) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.device_id}_refresh"
        self._attr_device_info = coordinator.build_device_info()

    async def async_press(self) -> None:
        await self._coordinator.async_request_refresh()
