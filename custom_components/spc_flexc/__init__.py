"""Home Assistant setup for the SPC FlexC integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .frontend import async_register_card
from .mapping_gate_coordinator import SpcFlexCMappingGateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up SPC FlexC."""
    try:
        await async_register_card(hass)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Could not register SPC FlexC dashboard card")

    coordinator = SpcFlexCMappingGateCoordinator(hass, entry)
    await coordinator.async_restore_panel_tamper()
    await coordinator.async_restore_area_history()

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

    # Apply alias changes after saving integration options.
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )

    # Do not await this. Platforms are already loaded and their coordinator
    # listeners can create dynamic entities as discovery completes.
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


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when user display aliases are changed."""
    await hass.config_entries.async_reload(entry.entry_id)
