"""Constants for moen_smart_water_network."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

NAME = "Moen Smart Water Network"
CLIENT = "client"
DOMAIN = "moen_smart_water_network"
VERSION = "0.0.1"

CONF_REFRESH_TOKEN = "refresh_token"  # noqa: S105
CONF_ZONE_DURATIONS = "zone_durations"
DEFAULT_MANUAL_RUN_DURATION = 5  # minutes
