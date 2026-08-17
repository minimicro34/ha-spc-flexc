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

SPC_ZONE_TYPES: dict[int, str] = {
    0: "alarm",
    1: "entry_exit",
    2: "exit_terminator",
    3: "fire",
    4: "emergency_exit",
    5: "line",
    6: "panic",
    7: "hold_up",
    8: "tamper",
    9: "technical",
    10: "medical",
    11: "keyswitch",
    13: "shunt",
    14: "x_shunt",
    15: "detector_fault",
    16: "locking_supervision",
    18: "all_well",
    19: "hold_up_fault",
    20: "warning_fault",
    21: "set_unset_authorization",
    22: "locking_element",
    23: "glass_break",
    24: "water",
    25: "heat",
    26: "fridge_freezer",
    27: "gas",
    28: "sprinkler",
    29: "co2",
    30: "entry_exit_2",
}
