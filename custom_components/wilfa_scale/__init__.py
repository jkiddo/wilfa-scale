"""The Wilfa Svart Scale integration."""

from __future__ import annotations

import logging

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import WilfaScaleCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Wilfa Svart Scale from a config entry."""
    address: str = entry.data[CONF_ADDRESS]

    ble_device = bluetooth.async_ble_device_from_address(
        hass, address, connectable=True
    )
    if not ble_device:
        _LOGGER.error("Could not find Wilfa scale with address %s", address)
        return False

    coordinator = WilfaScaleCoordinator(hass, ble_device)
    connected = await coordinator.connect()
    if not connected:
        _LOGGER.error("Failed to connect to Wilfa scale at %s", address)
        return False

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: WilfaScaleCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.disconnect()
    return unload_ok
