async def async_get_config_entry_diagnostics(hass, entry):
    c = entry.runtime_data
    return {
        "connected": c.client.connected,
        "panel": c.data.panel.raw,
        "areas": c.data.areas,
        "zones": c.data.zones,
        "faults": vars(c.data.faults),
    }
