# Moen Smart Water Network

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
[![Community Forum][forum-shield]][forum]

Home Assistant custom integration for **Moen Smart Water Network** irrigation
controllers. Talks to Moen's cloud API for configuration and uses AWS IoT MQTT
device shadows for real-time state updates.

> ⚠️ **Unofficial.** This project is not affiliated with, endorsed by, or
> supported by Moen. It is built on top of an undocumented API which may change
> or break at any time.

## Features

- Real-time irrigation status via AWS IoT MQTT device shadow and `/async` topics
- Per-zone valve and switch entities with configurable run durations
- Manual watering service for one or more zones
- Schedule monitoring and a calendar entity for upcoming runs
- Sensors for connectivity (RSSI), watering mode, currently running zone, and
  remaining run time
- Binary sensors for rain sensor, master valve, flow sensor, and active schedule

## Supported devices

This integration has been developed and tested against the **Moen Smart Water
Irrigation Controller** (the 12-zone model paired with the Moen Smart Water
mobile app). Other Moen Smart Water products that share the same cloud /
device-shadow API may also work but are unverified — please open an issue if
you have one.

## Platforms

| Platform        | Description                                                     |
| --------------- | --------------------------------------------------------------- |
| `binary_sensor` | Connectivity, watering, rain sensor, master valve, flow sensor  |
| `calendar`      | Upcoming scheduled irrigation runs                              |
| `number`        | Per-zone manual run duration                                    |
| `sensor`        | Device state, RSSI, running zone, next run, run remaining, mode |
| `switch`        | Zone enable/disable, manual zone run                            |
| `valve`         | Zone valve open/close                                           |

## Services

| Service                                   | Description                           |
| ----------------------------------------- | ------------------------------------- |
| `moen_smart_water_network.start_watering` | Start a manual watering run on a zone |

## Installation

### HACS (recommended)

1. In Home Assistant, go to **HACS** → **Integrations** → menu (⋮) → **Custom
   repositories**.
2. Add `https://github.com/mattatcha/moen-smart-water-hass` as type
   **Integration**.
3. Install **Moen Smart Water Network** from the HACS list.
4. Restart Home Assistant.
5. Go to **Settings** → **Devices & Services** → **Add Integration** and search
   for *Moen Smart Water Network*.

### Manual

1. Copy `custom_components/moen_smart_water_network/` into your Home Assistant
   `config/custom_components/` directory.
2. Restart Home Assistant.
3. Add the integration via **Settings** → **Devices & Services**.

## Configuration

Configuration is done entirely through the Home Assistant UI. You will be
asked for two values:

- **Access token** — short-lived bearer token for the Moen API
- **Refresh token** — long-lived token used to renew the access token

The integration handles token renewal automatically. If renewal eventually
fails (for example because you signed out of the mobile app or rotated your
password), Home Assistant will surface a **Reauthenticate** prompt and you can
paste new tokens without removing the integration.

### Obtaining tokens

Moen does not currently expose a developer API or OAuth client for third-party
integrations, so tokens have to be extracted from a signed-in session of the
Moen Smart Water mobile app. The high-level approach:

1. Install a TLS-intercepting HTTP proxy (e.g.
   [mitmproxy](https://mitmproxy.org/), [Charles](https://www.charlesproxy.com/),
   or [Proxyman](https://proxyman.io/)) and trust its CA on your phone.
2. Route your phone's traffic through the proxy.
3. Sign in to the Moen Smart Water app and look for a `POST` to the Moen OAuth
   endpoint (`/oauth2/token` on `api.prod.iot.moen.com`).
4. The JSON response contains `access_token` and `refresh_token` — paste both
   into the Home Assistant config flow.

If you regenerate tokens (e.g. by signing out of the app), use the
**Reauthenticate** action in Home Assistant to update them.

## Real-time updates

The integration prefers push over polling:

- An **MQTT subscription** to each device's AWS IoT shadow delivers reported
  state changes (watering on/off, zone activations, sensor state) within
  seconds.
- A `/async/{duid}` topic delivers irrigation run progress (active zone,
  duration remaining).
- A periodic poll every 30 seconds backfills device metadata and schedules in
  case any MQTT messages were missed.

## Troubleshooting

### Enable debug logs

Add the following to `configuration.yaml` and restart:

```yaml
logger:
  default: info
  logs:
    custom_components.moen_smart_water_network: debug
```

Then reproduce the problem and download the **Diagnostics** dump from the
integration's device page. Tokens and account identifiers are redacted
automatically.

### Common issues

| Symptom                                     | Likely cause / fix                                                                       |
| ------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Setup fails with *Invalid auth credentials* | Refresh token has been revoked — sign in to the app again and obtain new tokens.         |
| Setup fails with *Failed to connect*        | Network/DNS issue reaching `api.prod.iot.moen.com` from Home Assistant.                  |
| Entities show as *unavailable*              | The device is offline or has lost Wi-Fi. Check the controller's status in the Moen app.  |
| State updates feel slow                     | MQTT may not be connected — restart the integration and check logs for `mqtt` messages.  |
| Reauth prompt keeps appearing               | Token rotation kicked you out — paste fresh tokens from the app once more.               |

When opening an issue, please include the diagnostics dump and a debug log.

## Architecture

The integration is split into a self-contained API package and standard Home
Assistant glue:

- **`moen_api/auth`** — OAuth2 token lifecycle and AWS Cognito credential
  provider for MQTT
- **`moen_api/client`** — REST client for devices, zones, schedules, and
  manual irrigation runs
- **`moen_api/mqtt`** — AWS IoT MQTT connection (shadow + `/async` topics) for
  real-time updates
- **`moen_api/models`** — TypedDict definitions for the API payload shapes
- **`coordinator`** — `DataUpdateCoordinator` that merges polled and pushed
  state and exposes computed properties to entities

## Contributing

Contributions are welcome! Please read the
[contribution guidelines](CONTRIBUTING.md) and run the linter (`uv tool run
ruff check .`) and tests (`uv run pytest`) before opening a pull request.

## Disclaimer

"Moen" is a trademark of its respective owner. This project is an independent,
community-maintained integration and uses an undocumented API at your own risk.

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
