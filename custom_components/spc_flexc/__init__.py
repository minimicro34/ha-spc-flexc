from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import SpcFlexCCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up SPC FlexC."""
    coordinator = SpcFlexCCoordinator(hass, entry)

    # Fast first refresh:
    # connection + PANEL_SUMMARY only.
    await coordinator.async_config_entry_first_refresh()

    serial = coordinator.data.panel.serial_number

    if serial and entry.unique_id != str(serial):
        hass.config_entries.async_update_entry(
            entry,
            unique_id=str(serial),
        )

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )

    # Do not await this.
    #
    # Platforms are already loaded and their coordinator listeners are
    # registered. Background discovery of ATS, areas and zones can therefore
    # create dynamic entities as soon as data becomes available.
    coordinator.async_start_background_discovery()

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Unload SPC FlexC."""
    ok = await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )

    if ok:
        await entry.runtime_data.async_shutdown()

    return ok
