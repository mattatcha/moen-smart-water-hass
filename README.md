# Moen Smart Water Network

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
[![Community Forum][forum-shield]][forum]

Home Assistant custom integration for Moen Smart Water Network irrigation controllers. Communicates with Moen's IoT API and uses AWS IoT MQTT for real-time device state updates.

## Features

- Real-time irrigation status via AWS IoT MQTT shadow and `/async` topics
- Zone enable/disable controls
- Schedule monitoring
- Device connectivity and watering state sensors
- Manual watering service

## Platforms

| Platform        | Description                                          |
| --------------- | ---------------------------------------------------- |
| `binary_sensor` | Device connectivity and watering state               |
| `sensor`        | Device status, currently running zone                |
| `switch`        | Zone enable/disable, zone run status, schedule state |

## Services

| Service                                     | Description                              |
| ------------------------------------------- | ---------------------------------------- |
| `moen_smart_water_network.start_watering`   | Start a manual watering run on a zone    |

## Installation

1. Copy the `custom_components/moen_smart_water_network/` directory into your Home Assistant `custom_components/` folder.
2. Restart Home Assistant.
3. Go to **Settings** -> **Devices & Services** -> **Add Integration** and search for "Moen Smart Water Network".
4. Enter your Moen OAuth2 access token and refresh token.

### HACS (recommended)

Add this repository as a custom repository in HACS, then install from there.

## Configuration

Configuration is done via the Home Assistant UI. You will need:

- **Access token** from Moen's OAuth2 flow
- **Refresh token** for automatic token renewal

Tokens can be obtained by intercepting the Moen mobile app's API traffic.

## Architecture

The integration uses a standalone `moen_api` package that separates:

- **`auth`** — OAuth2 token management and AWS Cognito credential provisioning
- **`client`** — REST API client for devices, zones, schedules, and irrigation
- **`mqtt`** — MQTT connection with shadow topics and `/async/{DUID}` for real-time irrigation run updates
- **`models`** — TypedDict definitions for all API data structures

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)

---

[moen_smart_water_network]: https://github.com/mattatcha/moen-smart-water-hass
[commits-shield]: https://img.shields.io/github/commit-activity/y/mattatcha/moen-smart-water-hass.svg?style=for-the-badge
[commits]: https://github.com/mattatcha/moen-smart-water-hass/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/mattatcha/moen-smart-water-hass.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/mattatcha/moen-smart-water-hass.svg?style=for-the-badge
[releases]: https://github.com/mattatcha/moen-smart-water-hass/releases
