"""BLE coordinator for the Wilfa Svart Scale."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from bleak import BleakClient
from bleak.backends.device import BLEDevice

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback

from .const import (
    NOTIFY_CHARACTERISTIC_UUID,
    RESP_BATTERY_LOW,
    RESP_DISCONNECT,
    RESP_OVERLOAD,
    RESP_UNIT_CHANGE,
    RESP_UNSTABLE,
    RESP_WEIGHT,
    UNIT_MAP,
    WRITE_CHARACTERISTIC_UUID,
    CMD_TARE,
    CMD_UNIT_GRAMS,
)

_LOGGER = logging.getLogger(__name__)

RECONNECT_INTERVAL = 30  # seconds between reconnect attempts


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

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        self.hass = hass
        self._address = address
        self._client: BleakClient | None = None
        self.data = WilfaScaleData()
        self._listeners: list[callback] = []
        self._prev_data: bytes | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._shutting_down = False
        self._expected_disconnect = False

    @property
    def address(self) -> str:
        return self._address

    @property
    def name(self) -> str:
        return "Wilfa Svart Scale"

    def _get_ble_device(self) -> BLEDevice | None:
        """Get a fresh BLE device reference from HA's bluetooth stack."""
        return bluetooth.async_ble_device_from_address(
            self.hass, self._address, connectable=True
        )

    def add_listener(self, update_callback: callback) -> None:
        self._listeners.append(update_callback)

    def remove_listener(self, update_callback: callback) -> None:
        self._listeners.remove(update_callback)

    def _notify_listeners(self) -> None:
        for listener in self._listeners:
            listener()

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
            self._expected_disconnect = True
            asyncio.ensure_future(self._handle_scale_disconnect())
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

    async def _handle_scale_disconnect(self) -> None:
        """Handle the scale sending a disconnect message - disconnect and start reconnect."""
        await self._disconnect_client()
        self.data.connected = False
        self._notify_listeners()
        self._schedule_reconnect()

    async def connect(self) -> bool:
        """Connect to the Wilfa scale via BLE."""
        self._cancel_reconnect()
        try:
            ble_device = self._get_ble_device()
            if not ble_device:
                _LOGGER.debug("Wilfa scale not found in BLE scan, will retry later")
                return False

            self._client = BleakClient(
                ble_device,
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
            self._expected_disconnect = False
            self._notify_listeners()
            _LOGGER.info("Connected to Wilfa scale: %s", self._address)
            return True

        except Exception:
            _LOGGER.debug("Failed to connect to Wilfa scale, will retry", exc_info=True)
            self.data.connected = False
            self._notify_listeners()
            return False

    async def _disconnect_client(self) -> None:
        """Disconnect the BLE client without triggering reconnect."""
        if self._client:
            self._expected_disconnect = True
            try:
                if self._client.is_connected:
                    await self._client.disconnect()
            except Exception:
                _LOGGER.debug("Error disconnecting client", exc_info=True)
            self._client = None

    async def disconnect(self) -> None:
        """Disconnect and stop all reconnection attempts (for unload)."""
        self._shutting_down = True
        self._cancel_reconnect()
        await self._disconnect_client()
        self.data.connected = False
        self._notify_listeners()
        _LOGGER.info("Disconnected from Wilfa scale")

    def _on_disconnect(self, client: BleakClient) -> None:
        """Handle unexpected BLE disconnection - schedule reconnect."""
        _LOGGER.info("Wilfa scale BLE disconnected (expected=%s)", self._expected_disconnect)
        self._client = None
        self.data.connected = False
        self._notify_listeners()

        if not self._expected_disconnect and not self._shutting_down:
            self._schedule_reconnect()
        self._expected_disconnect = False

    def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt."""
        if self._shutting_down:
            return
        self._cancel_reconnect()
        self._reconnect_task = self.hass.async_create_task(self._reconnect_loop())

    def _cancel_reconnect(self) -> None:
        """Cancel any pending reconnect task."""
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            self._reconnect_task = None

    async def _reconnect_loop(self) -> None:
        """Periodically attempt to reconnect to the scale."""
        while not self._shutting_down:
            _LOGGER.debug(
                "Attempting to reconnect to Wilfa scale in %s seconds",
                RECONNECT_INTERVAL,
            )
            await asyncio.sleep(RECONNECT_INTERVAL)
            if self._shutting_down:
                break
            if self._client and self._client.is_connected:
                break
            connected = await self.connect()
            if connected:
                _LOGGER.info("Successfully reconnected to Wilfa scale")
                break

    async def start(self) -> None:
        """Start the coordinator - connect or schedule reconnect."""
        connected = await self.connect()
        if not connected:
            _LOGGER.info(
                "Wilfa scale not available yet, will keep trying every %ss",
                RECONNECT_INTERVAL,
            )
            self._schedule_reconnect()

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
