"""Config flow for Store App Version."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_APP_ID,
    CONF_COUNTRY,
    CONF_PLATFORM,
    CONF_SCAN_INTERVAL,
    DEFAULT_COUNTRY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    PLATFORM_APP_STORE,
    PLATFORM_LABELS,
    PLATFORM_PLAY_STORE,
)

PLATFORM_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            selector.SelectOptionDict(
                value=PLATFORM_APP_STORE, label=PLATFORM_LABELS[PLATFORM_APP_STORE]
            ),
            selector.SelectOptionDict(
                value=PLATFORM_PLAY_STORE, label=PLATFORM_LABELS[PLATFORM_PLAY_STORE]
            ),
        ],
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)

INTERVAL_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=MIN_SCAN_INTERVAL,
        max=MAX_SCAN_INTERVAL,
        step=1,
        unit_of_measurement="min",
        mode=selector.NumberSelectorMode.BOX,
    )
)


def _normalize_country(value: str) -> str:
    return (value or DEFAULT_COUNTRY).strip().lower()


class StoreAppVersionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Store App Version."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            platform = user_input[CONF_PLATFORM]
            app_id = user_input[CONF_APP_ID].strip()
            country = _normalize_country(user_input[CONF_COUNTRY])
            scan_interval = int(user_input[CONF_SCAN_INTERVAL])

            unique_id = f"{platform}_{app_id}_{country}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            title = f"{app_id} ({PLATFORM_LABELS[platform]})"
            return self.async_create_entry(
                title=title,
                data={
                    CONF_PLATFORM: platform,
                    CONF_APP_ID: app_id,
                    CONF_COUNTRY: country,
                    CONF_SCAN_INTERVAL: scan_interval,
                },
            )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_PLATFORM, default=PLATFORM_APP_STORE
                ): PLATFORM_SELECTOR,
                vol.Required(CONF_APP_ID): str,
                vol.Required(CONF_COUNTRY, default=DEFAULT_COUNTRY): str,
                vol.Required(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): INTERVAL_SELECTOR,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return StoreAppVersionOptionsFlow(config_entry)


class StoreAppVersionOptionsFlow(OptionsFlow):
    """Allow editing country and scan interval after setup."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_COUNTRY: _normalize_country(user_input[CONF_COUNTRY]),
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                },
            )

        current_country = self.config_entry.options.get(
            CONF_COUNTRY,
            self.config_entry.data.get(CONF_COUNTRY, DEFAULT_COUNTRY),
        )
        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )

        schema = vol.Schema(
            {
                vol.Required(CONF_COUNTRY, default=current_country): str,
                vol.Required(
                    CONF_SCAN_INTERVAL, default=current_interval
                ): INTERVAL_SELECTOR,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
