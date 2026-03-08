"""Sensor platform for Wilfa Svart Scale."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfMass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import WilfaScaleCoordinator

_LOGGER = logging.getLogger(__name__)

UNIT_HA_MAP = {
    "g": UnitOfMass.GRAMS,
    "oz": UnitOfMass.OUNCES,
    "lb": UnitOfMass.POUNDS,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Wilfa scale sensors from a config entry."""
    coordinator: WilfaScaleCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        WilfaWeightSensor(coordinator, entry),
        WilfaBatteryLowSensor(coordinator, entry),
    ])


class WilfaWeightSensor(SensorEntity):
    """Sensor for the scale weight reading."""

    _attr_has_entity_name = True
    _attr_name = "Weight"
    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfMass.GRAMS

    def __init__(
        self, coordinator: WilfaScaleCoordinator, entry: ConfigEntry
    ) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.address}_weight"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            name=coordinator.name,
            manufacturer="Wilfa",
            model="Svart Scale",
        )

    async def async_added_to_hass(self) -> None:
        self._coordinator.add_listener(self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        self._coordinator.remove_listener(self._handle_update)

    @callback
    def _handle_update(self) -> None:
        self._attr_native_value = self._coordinator.data.weight
        ha_unit = UNIT_HA_MAP.get(self._coordinator.data.unit, UnitOfMass.GRAMS)
        self._attr_native_unit_of_measurement = ha_unit
        self._attr_available = self._coordinator.data.connected
        self._attr_extra_state_attributes = {
            "unstable": self._coordinator.data.unstable,
            "overload": self._coordinator.data.overload,
        }
        self.async_write_ha_state()

    @property
    def native_value(self) -> float | None:
        return self._coordinator.data.weight

    @property
    def available(self) -> bool:
        return self._coordinator.data.connected


class WilfaBatteryLowSensor(SensorEntity):
    """Binary-style sensor for battery low indication."""

    _attr_has_entity_name = True
    _attr_name = "Battery Low"
    _attr_icon = "mdi:battery-alert"

    def __init__(
        self, coordinator: WilfaScaleCoordinator, entry: ConfigEntry
    ) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.address}_battery_low"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            name=coordinator.name,
            manufacturer="Wilfa",
            model="Svart Scale",
        )

    async def async_added_to_hass(self) -> None:
        self._coordinator.add_listener(self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        self._coordinator.remove_listener(self._handle_update)

    @callback
    def _handle_update(self) -> None:
        self._attr_native_value = "Low" if self._coordinator.data.battery_low else "OK"
        self._attr_available = self._coordinator.data.connected
        self.async_write_ha_state()

    @property
    def native_value(self) -> str:
        return "Low" if self._coordinator.data.battery_low else "OK"

    @property
    def available(self) -> bool:
        return self._coordinator.data.connected
