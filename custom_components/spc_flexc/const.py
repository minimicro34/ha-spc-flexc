"""Constants for the SPC FlexC integration."""

from homeassistant.const import Platform

DOMAIN = "spc_flexc"

PLATFORMS = (
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
)

DEFAULT_PORT = 52000
DEFAULT_ZONE_INTERVAL = 1.0
DEFAULT_AREA_INTERVAL = 1.0
DEFAULT_PANEL_INTERVAL = 60.0

CONF_PORT = "port"
CONF_KEY = "encryption_key"
CONF_COMMAND_USERNAME = "command_username"
CONF_COMMAND_PASSWORD = "command_password"

ATS_IDS = range(1, 5)
AREA_IDS = range(1, 9)
ZONE_IDS = range(1, 9)
