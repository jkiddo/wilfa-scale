"""BLE coordinator for the Wilfa Svart Scale."""

from __future__ import annotations

import asyncio
import logging
import struct
from datetime import datetime
from typing import Any

from bleak import BleakClient
from bleak.backends.device import BLEDevice

from homeassistant.core import HomeAssistant, callback

from .const import (
    DISCONNECT_TIMEOUT,
    NOTIFY_CHARACTERISTIC_UUID,
    RESP_BATTERY_LOW,
    RESP_DISCONNECT,
    RESP_OVERLOAD,
    RESP_UNIT_CHANGE,
    RESP_UNSTABLE,
    RESP_WEIGHT,
    SERVICE_UUID,
    UNIT_MAP,
    WRITE_CHARACTERISTIC_UUID,
    CMD_TARE,
    CMD_UNIT_GRAMS,
)

_LOGGER = logging.getLogger(__name__)


class WilfaScaleData:
    """Represents the current state of the Wilfa scale."""

    def __init__(self) -> None:
        self.weight: float | None = None
        self.unit: str = "g"
        self.battery_low: bool = False
        self.unstable: bool = False
        self.overload: bool = False
        self.connected: bool = False
        self.last_update: datetime | None = None


class WilfaScaleCoordinator:
    """Manages BLE connection and data parsing for the Wilfa Svart Scale."""

    def __init__(self, hass: HomeAssistant, ble_device: BLEDevice) -> None:
        self.hass = hass
        self.ble_device = ble_device
        self._client: BleakClient | None = None
        self.data = WilfaScaleData()
        self._listeners: list[callback] = []
        self._disconnect_timer: asyncio.TimerHandle | None = None
        self._prev_data: bytes | None = None

    @property
    def address(self) -> str:
        return self.ble_device.address

    @property
    def name(self) -> str:
        return self.ble_device.name or "Wilfa Svart Scale"

    def add_listener(self, update_callback: callback) -> None:
        self._listeners.append(update_callback)

    def remove_listener(self, update_callback: callback) -> None:
        self._listeners.remove(update_callback)

    def _notify_listeners(self) -> None:
        for listener in self._listeners:
            listener()

    def _reset_disconnect_timer(self) -> None:
        if self._disconnect_timer:
            self._disconnect_timer.cancel()
        self._disconnect_timer = self.hass.loop.call_later(
            DISCONNECT_TIMEOUT, lambda: asyncio.ensure_future(self.disconnect())
        )

    def _parse_weight(self, byte2: str, byte3: str) -> float:
        """Parse weight from two hex bytes, handling two's complement for negative values."""
        value = int(byte2 + byte3, 16)
        binary = bin(value)[2:]  # Remove '0b' prefix
        if len(binary) == 16 and binary[0] == "1":
            # Two's complement for negative values
            inverted = "".join("1" if b == "0" else "0" for b in binary[1:])
            value = -1 * (int(inverted, 2) + 1)
        return value / 10.0

    def _handle_notification(self, sender: Any, raw_data: bytearray) -> None:
        """Handle incoming BLE notification data."""
        if raw_data == self._prev_data:
            return
        self._prev_data = bytes(raw_data)

        hex_bytes = [f"{b:02x}" for b in raw_data]

        if len(hex_bytes) < 2:
            return

        self._reset_disconnect_timer()
        self.data.last_update = datetime.now()

        resp_type = hex_bytes[1]

        if resp_type == RESP_WEIGHT:
            if len(hex_bytes) >= 4:
                self.data.weight = self._parse_weight(hex_bytes[2], hex_bytes[3])
                self.data.unstable = False
                self.data.overload = False
                _LOGGER.debug("Weight: %.1f %s", self.data.weight, self.data.unit)

        elif resp_type == RESP_DISCONNECT:
            _LOGGER.info("Scale sent disconnect notification")
            asyncio.ensure_future(self.disconnect())
            return

        elif resp_type == RESP_UNIT_CHANGE:
            if len(hex_bytes) >= 3:
                self.data.unit = UNIT_MAP.get(hex_bytes[2], "g")
                _LOGGER.debug("Unit changed to: %s", self.data.unit)

        elif resp_type == RESP_BATTERY_LOW:
            self.data.battery_low = True
            _LOGGER.warning("Scale battery is low")

        elif resp_type == RESP_UNSTABLE:
            self.data.unstable = True

        elif resp_type == RESP_OVERLOAD:
            self.data.overload = True
            _LOGGER.warning("Scale is overloaded")

        self.data.connected = True
        self._notify_listeners()

    async def connect(self) -> bool:
        """Connect to the Wilfa scale via BLE."""
        try:
            self._client = BleakClient(
                self.ble_device,
                disconnected_callback=self._on_disconnect,
            )
            await self._client.connect(timeout=10.0)

            # Subscribe to notifications on both characteristics
            await self._client.start_notify(
                NOTIFY_CHARACTERISTIC_UUID, self._handle_notification
            )
            await self._client.start_notify(
                WRITE_CHARACTERISTIC_UUID, self._handle_notification
            )

            # Set unit to grams
            await self._client.write_gatt_char(
                WRITE_CHARACTERISTIC_UUID, CMD_UNIT_GRAMS, response=True
            )

            self.data.connected = True
            self._reset_disconnect_timer()
            self._notify_listeners()
            _LOGGER.info("Connected to Wilfa scale: %s", self.name)
            return True

        except Exception:
            _LOGGER.exception("Failed to connect to Wilfa scale")
            self.data.connected = False
            self._notify_listeners()
            return False

    async def disconnect(self) -> None:
        """Disconnect from the scale."""
        if self._disconnect_timer:
            self._disconnect_timer.cancel()
            self._disconnect_timer = None
        if self._client and self._client.is_connected:
            await self._client.disconnect()
        self.data.connected = False
        self._notify_listeners()
        _LOGGER.info("Disconnected from Wilfa scale")

    def _on_disconnect(self, client: BleakClient) -> None:
        """Handle unexpected disconnection."""
        _LOGGER.info("Wilfa scale disconnected")
        self.data.connected = False
        if self._disconnect_timer:
            self._disconnect_timer.cancel()
            self._disconnect_timer = None
        self._notify_listeners()

    async def tare(self) -> None:
        """Send tare (zero) command to the scale."""
        if self._client and self._client.is_connected:
            await self._client.write_gatt_char(
                WRITE_CHARACTERISTIC_UUID, CMD_TARE, response=True
            )
            _LOGGER.debug("Tare command sent")

    async def set_unit(self, unit: str) -> None:
        """Change the unit on the scale."""
        from .const import CMD_UNIT_GRAMS, CMD_UNIT_OUNCES, CMD_UNIT_POUNDS

        cmd_map = {"g": CMD_UNIT_GRAMS, "oz": CMD_UNIT_OUNCES, "lb": CMD_UNIT_POUNDS}
        cmd = cmd_map.get(unit)
        if cmd and self._client and self._client.is_connected:
            await self._client.write_gatt_char(
                WRITE_CHARACTERISTIC_UUID, cmd, response=True
            )
            _LOGGER.debug("Unit change command sent: %s", unit)
