"""Constants for the Wilfa Svart Scale integration."""

DOMAIN = "wilfa_scale"

# BLE UUIDs
SERVICE_UUID = "0000ffb0-0000-1000-8000-00805f9b34fb"
NOTIFY_CHARACTERISTIC_UUID = "0000ffb2-0000-1000-8000-00805f9b34fb"
WRITE_CHARACTERISTIC_UUID = "0000ffb1-0000-1000-8000-00805f9b34fb"

# Commands
CMD_TARE = bytes([0xF5, 0x10])
CMD_UNIT_GRAMS = bytes([0xF5, 0x11, 0x00])
CMD_UNIT_OUNCES = bytes([0xF5, 0x11, 0x01])
CMD_UNIT_POUNDS = bytes([0xF5, 0x11, 0x02])

# Response types (2nd byte)
RESP_WEIGHT = "01"
RESP_DISCONNECT = "03"
RESP_UNIT_CHANGE = "04"
RESP_BATTERY_LOW = "05"
RESP_UNSTABLE = "06"
RESP_OVERLOAD = "07"

# Unit mapping
UNIT_MAP = {
    "00": "g",
    "01": "oz",
    "02": "lb",
}

# Timeouts
CONNECTION_TIMEOUT = 10
DISCONNECT_TIMEOUT = 10
