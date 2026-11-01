"""Home Assistant setup for the SPC FlexC integration."""

import logging
import re

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

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
    except Exception:
        _LOGGER.exception("Could not register SPC FlexC dashboard card")

    coordinator = SpcFlexCMappingGateCoordinator(hass, entry)
    await coordinator.async_restore_panel_tamper()
    await coordinator.async_restore_area_history()

    # Fast first refresh:
    # connection + PANEL_SUMMARY only.
    try:
        await coordinator.async_config_entry_first_refresh()
    except BaseException:
        await coordinator.async_shutdown()
        raise

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

    # Remove stale zone entities only after the complete, successful discovery.
    # Restrict cleanup to the exact unique IDs owned by this config entry;
    # other entities (including renamed/customized entities) are untouched.
    zone_entity_pattern = re.compile(
        rf"^{re.escape(entry.entry_id)}_zone_(\d+)_(?:motion|tamper|trouble|inhibition|isolation|restore)$"
    )
    orphan_cleanup_done = False

    def cleanup_orphan_zones() -> None:
        nonlocal orphan_cleanup_done
        if orphan_cleanup_done or not coordinator._discovery_complete:
            return
        # An empty discovery is not sufficient evidence to delete all zones.
        discovered_zones = coordinator._detected_zone_ids
        if not discovered_zones:
            _LOGGER.warning("Skipping orphan zone cleanup: no zones discovered")
            return
        registry = er.async_get(hass)
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
            match = zone_entity_pattern.fullmatch(entity.unique_id)
            if not match or int(match.group(1)) in discovered_zones:
                continue
            # Never remove a currently loaded entity. Its platform owns its
            # lifecycle, even if a discovery result appears inconsistent.
            current_state = hass.states.get(entity.entity_id)
            if current_state is not None and current_state.state != STATE_UNAVAILABLE:
                _LOGGER.warning(
                    "Skipping orphan cleanup for active SPC entity %s",
                    entity.entity_id,
                )
                continue
            _LOGGER.info(
                "Removing orphan SPC zone entity %s (zone %s no longer discovered)",
                entity.entity_id,
                match.group(1),
            )
            registry.async_remove(entity.entity_id)
        orphan_cleanup_done = True

    entry.async_on_unload(coordinator.async_add_listener(cleanup_orphan_zones))

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
