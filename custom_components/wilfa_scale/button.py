"""Button platform for Wilfa Svart Scale (tare)."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import WilfaScaleCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Wilfa scale buttons from a config entry."""
    coordinator: WilfaScaleCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WilfaTareButton(coordinator, entry)])


class WilfaTareButton(ButtonEntity):
    """Button to tare (zero) the scale."""

    _attr_has_entity_name = True
    _attr_name = "Tare"
    _attr_icon = "mdi:scale-balance"

    def __init__(
        self, coordinator: WilfaScaleCoordinator, entry: ConfigEntry
    ) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.address}_tare"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            name=coordinator.name,
            manufacturer="Wilfa",
            model="Svart Scale",
        )

    @property
    def available(self) -> bool:
        return self._coordinator.data.connected

    async def async_press(self) -> None:
        """Send tare command to the scale."""
        await self._coordinator.tare()
