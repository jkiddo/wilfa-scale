# Wilfa Svart Scale - Home Assistant Integration

A custom [Home Assistant](https://www.home-assistant.io/) component that connects to the **Wilfa Svart** kitchen scale over Bluetooth Low Energy (BLE), providing real-time weight measurements and scale controls directly in your smart home.

## Features

- **Real-time weight tracking** via BLE push notifications (no polling)
- **Multi-unit support** — grams, ounces, and pounds
- **Tare (zero) button** to reset the scale from Home Assistant
- **Battery monitoring** — alerts when battery is low
- **Stability and overload indicators** exposed as sensor attributes
- **Auto-discovery** — detects Wilfa scales on your Bluetooth network
- **Automatic reconnection** with 30-second retry interval

## Requirements

- Home Assistant 2023.x or later
- A Bluetooth adapter supported by Home Assistant
- A Wilfa Svart kitchen scale

## Installation

### HACS (recommended)

1. Add this repository as a custom repository in [HACS](https://hacs.xyz/)
2. Search for "Wilfa Scale" and install
3. Restart Home Assistant

### Manual

1. Copy the `custom_components/wilfa_scale` directory into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Setup

The integration supports two setup methods:

- **Auto-discovery**: If your Wilfa scale is powered on and within Bluetooth range, Home Assistant will automatically detect it. A notification will appear asking you to confirm the device.
- **Manual**: Go to **Settings > Devices & Services > Add Integration**, search for "Wilfa Scale", and select your device from the list.

## Entities

| Entity | Type | Description |
|---|---|---|
| Weight | Sensor | Current weight reading with unit (g/oz/lb) |
| Battery Low | Sensor | Battery status ("OK" or "Low") |
| Tare | Button | Zeros the scale |

The weight sensor also exposes `unstable` and `overload` as extra state attributes.

## BLE Protocol

The integration communicates over a custom BLE GATT service (`0000ffb0-...`):

| Characteristic | Direction | UUID |
|---|---|---|
| Notify | Scale -> HA | `0000ffb2-0000-1000-8000-00805f9b34fb` |
| Write | HA -> Scale | `0000ffb1-0000-1000-8000-00805f9b34fb` |

### Commands

| Command | Bytes | Description |
|---|---|---|
| Tare | `F5 10` | Zero the scale |
| Set grams | `F5 11 00` | Switch unit to grams |
| Set ounces | `F5 11 01` | Switch unit to ounces |
| Set pounds | `F5 11 02` | Switch unit to pounds |

## License

[MIT](LICENSE) - Jens Kristian Villadsen
