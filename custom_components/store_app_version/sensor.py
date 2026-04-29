"""Sensor platform for Store App Version."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_APP_ID,
    CONF_PLATFORM,
    DOMAIN,
    PLATFORM_LABELS,
)
from .coordinator import StoreAppVersionCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: StoreAppVersionCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([StoreAppVersionSensor(coordinator, entry)])


class StoreAppVersionSensor(
    CoordinatorEntity[StoreAppVersionCoordinator], SensorEntity
):
    """Sensor exposing the current store version of an app."""

    _attr_has_entity_name = True
    _attr_name = "Version"
    _attr_icon = "mdi:cellphone-arrow-down"

    def __init__(
        self,
        coordinator: StoreAppVersionCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        platform = entry.data[CONF_PLATFORM]
        app_id = entry.data[CONF_APP_ID]
        country = coordinator.country
        device_id = f"{platform}_{app_id}_{country}"

        self._attr_unique_id = f"{device_id}_version"

        data = coordinator.data or {}
        app_name = data.get("name") or app_id
        platform_label = PLATFORM_LABELS.get(platform, platform)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=f"{app_name} ({platform_label})",
            manufacturer=data.get("developer") or platform_label,
            model=platform_label,
            configuration_url=data.get("url"),
            entry_type=None,
        )

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("version")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        return {
            "app_id": self._entry.data[CONF_APP_ID],
            "platform": PLATFORM_LABELS.get(self._entry.data[CONF_PLATFORM]),
            "country": self.coordinator.country,
            "name": data.get("name"),
            "developer": data.get("developer"),
            "released": data.get("released"),
            "release_notes": data.get("release_notes"),
            "min_os_version": data.get("min_os_version"),
            "size_bytes": data.get("size_bytes"),
            "rating": data.get("rating"),
            "rating_count": data.get("rating_count"),
            "url": data.get("url"),
            "icon": data.get("icon"),
            "installs": data.get("installs"),
        }
