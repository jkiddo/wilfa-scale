"""Config flow for Wilfa Svart Scale."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN, SERVICE_UUID

_LOGGER = logging.getLogger(__name__)


class WilfaScaleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wilfa Svart Scale."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or "Wilfa Svart Scale"
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        assert self._discovery_info is not None
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovery_info.name or "Wilfa Svart Scale",
                data={CONF_ADDRESS: self._discovery_info.address},
            )
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": self._discovery_info.name or "Wilfa Svart Scale"
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            discovery_info = self._discovered_devices[address]
            return self.async_create_entry(
                title=discovery_info.name or "Wilfa Svart Scale",
                data={CONF_ADDRESS: address},
            )

        current_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass, connectable=True):
            if discovery_info.address in current_addresses:
                continue
            name = discovery_info.name or ""
            if name.lower().startswith("wilfa"):
                self._discovered_devices[discovery_info.address] = discovery_info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            addr: f"{info.name} ({addr})"
                            for addr, info in self._discovered_devices.items()
                        }
                    ),
                }
            ),
        )
