"""Privacy-safe diagnostics for the SPC FlexC integration."""

from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data

# Redact all potentially identifying fields, including nested FlexC event payloads.
TO_REDACT = {
    "serial",
    "serial_number",
    "SERIAL",
    "SERIAL_NUMBER",
    "installation_name",
    "INSTALLATION_NAME",
    "name",
    "NAME",
    "user_name",
    "USER_NAME",
    "username",
    "USERNAME",
    "user_alias",
    "USER_ALIAS",
    "alias",
    "ALIAS",
    "last_set_user",
    "last_unset_user",
    "last_arm_user",
    "last_disarm_user",
    "last_set_user_name",
    "last_unset_user_name",
    "last_arm_user_name",
    "last_disarm_user_name",
    "last_set_user_alias",
    "last_unset_user_alias",
    "last_arm_user_alias",
    "last_disarm_user_alias",
}


async def async_get_config_entry_diagnostics(hass, entry):
    """Return diagnostics without exposing names or raw event payloads."""
    c = entry.runtime_data
    # Raw panel/area/zone data can contain names and event payloads with
    # user identities. Return aggregate state instead of leaking those values.
    data = {
        "connected": c.client.connected,
        "counts": {
            "areas": len(c.data.areas),
            "zones": len(c.data.zones),
            "doors": len(c.data.doors),
            "ats": len(c.data.ats),
            "xbus_devices": len(c.data.xbus_devices),
        },
        "faults": vars(c.data.faults),
    }
    return async_redact_data(data, TO_REDACT)
