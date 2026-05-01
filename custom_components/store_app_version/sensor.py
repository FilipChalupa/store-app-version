"""Sensor platform for Store App Version."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
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
    async_add_entities(
        [
            StoreAppVersionSensor(coordinator, entry),
            StoreAppLastRefreshSensor(coordinator),
        ]
    )


class StoreAppVersionSensor(
    CoordinatorEntity[StoreAppVersionCoordinator], RestoreSensor
):
    """Sensor exposing the current store version of an app."""

    _attr_has_entity_name = True
    _attr_translation_key = "version"
    _attr_icon = "mdi:cellphone-arrow-down"

    def __init__(
        self,
        coordinator: StoreAppVersionCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._restored_version: str | None = None
        self._attr_unique_id = f"{coordinator.device_id}_version"
        self._attr_device_info = coordinator.build_device_info()

    async def async_added_to_hass(self) -> None:
        """Restore last known version after a Home Assistant restart."""
        await super().async_added_to_hass()
        last_data = await self.async_get_last_sensor_data()
        if last_data is not None and last_data.native_value is not None:
            self._restored_version = str(last_data.native_value)

    @property
    def native_value(self) -> str | None:
        if self.coordinator.data:
            current = self.coordinator.data.get("version")
            if current:
                return current
        return self._restored_version

    @property
    def entity_picture(self) -> str | None:
        if self.coordinator.data:
            return self.coordinator.data.get("icon")
        return None

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


class StoreAppLastRefreshSensor(
    CoordinatorEntity[StoreAppVersionCoordinator], SensorEntity
):
    """Diagnostic sensor exposing the last successful fetch timestamp."""

    _attr_has_entity_name = True
    _attr_translation_key = "last_refresh"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, coordinator: StoreAppVersionCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_last_refresh"
        self._attr_device_info = coordinator.build_device_info()

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.last_successful_fetch
