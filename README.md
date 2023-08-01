# Moen Smart Water Network

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
[![Community Forum][forum-shield]][forum]

_Integration to integrate with [moen_smart_water_network][moen_smart_water_network]._

**This integration will set up the following platforms.**

| Platform        | Description                         |
| --------------- | ----------------------------------- |
| `binary_sensor` | Show something `True` or `False`.   |
| `sensor`        | Show info from blueprint API.       |
| `switch`        | Switch something `True` or `False`. |

## Installation

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
1. If you do not have a `custom_components` directory (folder) there, you need to create it.
1. In the `custom_components` directory (folder) create a new folder called `moen_smart_water_network`.
1. Download _all_ the files from the `custom_components/moen_smart_water_network/` directory (folder) in this repository.
1. Place the files you downloaded in the new directory (folder) you created.
1. Restart Home Assistant
1. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "Integration blueprint"

## Configuration is done in the UI

<!---->

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
