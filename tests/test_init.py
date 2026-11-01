"""Tests for SPC FlexC integration setup and unload."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.spc_flexc import async_setup_entry, async_unload_entry
from custom_components.spc_flexc.const import PLATFORMS


@pytest.mark.asyncio
async def test_setup_entry_initializes_and_starts_discovery() -> None:
    """Setup performs the first refresh, forwards platforms and starts discovery."""
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    entry = MagicMock()
    entry.entry_id = "spc-entry"
    entry.unique_id = None

    coordinator = MagicMock()
    coordinator.async_restore_panel_tamper = AsyncMock()
    coordinator.async_restore_area_history = AsyncMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.data.panel.serial_number = "SPC12345678"

    with (
        patch(
            "custom_components.spc_flexc.async_register_card", new_callable=AsyncMock
        ),
        patch(
            "custom_components.spc_flexc.SpcFlexCMappingGateCoordinator",
            return_value=coordinator,
        ),
    ):
        assert await async_setup_entry(hass, entry) is True

    coordinator.async_restore_panel_tamper.assert_awaited_once_with()
    coordinator.async_restore_area_history.assert_awaited_once_with()
    coordinator.async_config_entry_first_refresh.assert_awaited_once_with()
    hass.config_entries.async_update_entry.assert_called_once_with(
        entry, unique_id="SPC12345678"
    )
    assert entry.runtime_data is coordinator
    hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(
        entry, PLATFORMS
    )
    coordinator.async_start_background_discovery.assert_called_once_with()


@pytest.mark.asyncio
async def test_setup_entry_keeps_existing_serial() -> None:
    """Setup does not rewrite an entry that already has the panel serial."""
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    entry = MagicMock()
    entry.entry_id = "spc-entry"
    entry.unique_id = "SPC12345678"

    coordinator = MagicMock()
    coordinator.async_restore_panel_tamper = AsyncMock()
    coordinator.async_restore_area_history = AsyncMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.data.panel.serial_number = "SPC12345678"

    with patch(
        "custom_components.spc_flexc.SpcFlexCMappingGateCoordinator",
        return_value=coordinator,
    ):
        assert await async_setup_entry(hass, entry) is True

    hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("unload_ok", [True, False])
async def test_unload_entry_shutdown_only_after_success(unload_ok: bool) -> None:
    """Coordinator shutdown follows successful platform unload only."""
    hass = MagicMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=unload_ok)
    entry = MagicMock()
    entry.runtime_data.async_shutdown = AsyncMock()

    assert await async_unload_entry(hass, entry) is unload_ok

    hass.config_entries.async_unload_platforms.assert_awaited_once_with(
        entry, PLATFORMS
    )
    if unload_ok:
        entry.runtime_data.async_shutdown.assert_awaited_once_with()
    else:
        entry.runtime_data.async_shutdown.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", [RuntimeError("panel unavailable"), asyncio.CancelledError()]
)
async def test_failed_first_refresh_closes_listener(failure: BaseException) -> None:
    """A failed or cancelled first refresh must release the TCP listener."""
    hass = MagicMock()
    entry = MagicMock()
    coordinator = MagicMock()
    coordinator.async_restore_panel_tamper = AsyncMock()
    coordinator.async_restore_area_history = AsyncMock()
    coordinator.async_config_entry_first_refresh = AsyncMock(side_effect=failure)
    coordinator.async_shutdown = AsyncMock()

    with (
        patch(
            "custom_components.spc_flexc.async_register_card", new_callable=AsyncMock
        ),
        patch(
            "custom_components.spc_flexc.SpcFlexCMappingGateCoordinator",
            return_value=coordinator,
        ),
        pytest.raises(type(failure)),
    ):
        await async_setup_entry(hass, entry)

    coordinator.async_shutdown.assert_awaited_once_with()
    assert entry.runtime_data is not coordinator


@pytest.mark.asyncio
async def test_orphan_zone_cleanup_requires_complete_discovery() -> None:
    """Only stale zone entities belonging to this entry are removed."""
    hass = MagicMock()
    hass.states.get.return_value = None
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    entry = MagicMock()
    entry.entry_id = "spc-entry"
    entry.unique_id = "SPC12345678"
    coordinator = MagicMock()
    coordinator.async_restore_panel_tamper = AsyncMock()
    coordinator.async_restore_area_history = AsyncMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.data.panel.serial_number = "SPC12345678"
    coordinator._discovery_complete = False
    coordinator._detected_zone_ids = {1, 2}

    entities = [
        MagicMock(
            entity_id="binary_sensor.zone_1", unique_id="spc-entry_zone_1_motion"
        ),
        MagicMock(
            entity_id="binary_sensor.zone_13", unique_id="spc-entry_zone_13_motion"
        ),
        MagicMock(entity_id="switch.zone_13", unique_id="spc-entry_zone_13_isolation"),
        MagicMock(entity_id="button.zone_13", unique_id="spc-entry_zone_13_restore"),
        MagicMock(entity_id="sensor.unrelated", unique_id="other-entry_zone_13_motion"),
        MagicMock(entity_id="sensor.door", unique_id="spc-entry_door_13_status"),
    ]
    registry = MagicMock()
    with (
        patch(
            "custom_components.spc_flexc.SpcFlexCMappingGateCoordinator",
            return_value=coordinator,
        ),
        patch("custom_components.spc_flexc.er.async_get", return_value=registry),
        patch(
            "custom_components.spc_flexc.er.async_entries_for_config_entry",
            return_value=entities,
        ),
    ):
        assert await async_setup_entry(hass, entry)
        listener = coordinator.async_add_listener.call_args.args[0]
        listener()
        registry.async_remove.assert_not_called()
        coordinator._discovery_complete = True
        listener()
        assert {call.args[0] for call in registry.async_remove.call_args_list} == {
            "binary_sensor.zone_13",
            "switch.zone_13",
            "button.zone_13",
        }
        listener()
        assert registry.async_remove.call_count == 3


@pytest.mark.asyncio
async def test_orphan_zone_cleanup_skips_empty_discovery() -> None:
    """An unexpectedly empty scan cannot wipe the zone registry."""
    hass = MagicMock()
    hass.states.get.return_value = None
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    entry = MagicMock()
    entry.entry_id = "spc-entry"
    entry.unique_id = "SPC12345678"
    coordinator = MagicMock()
    coordinator.async_restore_panel_tamper = AsyncMock()
    coordinator.async_restore_area_history = AsyncMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.data.panel.serial_number = "SPC12345678"
    coordinator._discovery_complete = True
    coordinator._detected_zone_ids = set()
    registry = MagicMock()
    with (
        patch(
            "custom_components.spc_flexc.SpcFlexCMappingGateCoordinator",
            return_value=coordinator,
        ),
        patch("custom_components.spc_flexc.er.async_get", return_value=registry),
    ):
        assert await async_setup_entry(hass, entry)
        listener = coordinator.async_add_listener.call_args.args[0]
        listener()
        registry.async_remove.assert_not_called()


@pytest.mark.asyncio
async def test_orphan_cleanup_preserves_active_entities() -> None:
    """Never remove an entity that is still present in the HA state machine."""
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.states.get.return_value = MagicMock(state="on")
    entry = MagicMock()
    entry.entry_id = "spc-entry"
    entry.unique_id = "SPC12345678"
    coordinator = MagicMock()
    coordinator.async_restore_panel_tamper = AsyncMock()
    coordinator.async_restore_area_history = AsyncMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.data.panel.serial_number = "SPC12345678"
    coordinator._discovery_complete = True
    coordinator._detected_zone_ids = {1}
    registry = MagicMock()
    stale = MagicMock(
        entity_id="binary_sensor.zone_13",
        unique_id="spc-entry_zone_13_motion",
    )
    with (
        patch(
            "custom_components.spc_flexc.SpcFlexCMappingGateCoordinator",
            return_value=coordinator,
        ),
        patch("custom_components.spc_flexc.er.async_get", return_value=registry),
        patch(
            "custom_components.spc_flexc.er.async_entries_for_config_entry",
            return_value=[stale],
        ),
    ):
        assert await async_setup_entry(hass, entry)
        coordinator.async_add_listener.call_args.args[0]()
        registry.async_remove.assert_not_called()


@pytest.mark.asyncio
async def test_orphan_cleanup_removes_unavailable_entities() -> None:
    """Remove a stale zone when its HA state is unavailable."""
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.states.get.return_value = MagicMock(state="unavailable")
    entry = MagicMock()
    entry.entry_id = "spc-entry"
    entry.unique_id = "SPC12345678"
    coordinator = MagicMock()
    coordinator.async_restore_panel_tamper = AsyncMock()
    coordinator.async_restore_area_history = AsyncMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.data.panel.serial_number = "SPC12345678"
    coordinator._discovery_complete = True
    coordinator._detected_zone_ids = {1}
    registry = MagicMock()
    stale = MagicMock(
        entity_id="binary_sensor.zone_13",
        unique_id="spc-entry_zone_13_motion",
    )
    with (
        patch(
            "custom_components.spc_flexc.SpcFlexCMappingGateCoordinator",
            return_value=coordinator,
        ),
        patch("custom_components.spc_flexc.er.async_get", return_value=registry),
        patch(
            "custom_components.spc_flexc.er.async_entries_for_config_entry",
            return_value=[stale],
        ),
    ):
        assert await async_setup_entry(hass, entry)
        coordinator.async_add_listener.call_args.args[0]()
        registry.async_remove.assert_called_once_with("binary_sensor.zone_13")


@pytest.mark.asyncio
async def test_orphan_area_cleanup_removes_unavailable_area_only() -> None:
    """Remove a missing area without touching discovered or unrelated entities."""
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.states.get.return_value = MagicMock(state="unavailable")
    entry = MagicMock()
    entry.entry_id = "spc-entry"
    entry.unique_id = "SPC12345678"
    coordinator = MagicMock()
    coordinator.async_restore_panel_tamper = AsyncMock()
    coordinator.async_restore_area_history = AsyncMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.data.panel.serial_number = "SPC12345678"
    coordinator._discovery_complete = True
    coordinator._detected_zone_ids = {1}
    coordinator._detected_area_ids = {1, 2}
    entities = [
        MagicMock(entity_id="alarm_control_panel.test", unique_id="spc-entry_area_13"),
        MagicMock(entity_id="alarm_control_panel.home", unique_id="spc-entry_area_1"),
        MagicMock(entity_id="alarm_control_panel.other", unique_id="other_area_13"),
    ]
    registry = MagicMock()
    with (
        patch(
            "custom_components.spc_flexc.SpcFlexCMappingGateCoordinator",
            return_value=coordinator,
        ),
        patch("custom_components.spc_flexc.er.async_get", return_value=registry),
        patch(
            "custom_components.spc_flexc.er.async_entries_for_config_entry",
            return_value=entities,
        ),
    ):
        assert await async_setup_entry(hass, entry)
        coordinator.async_add_listener.call_args.args[0]()
        registry.async_remove.assert_called_once_with("alarm_control_panel.test")


@pytest.mark.asyncio
async def test_orphan_area_cleanup_skips_empty_area_discovery() -> None:
    """Do not prune areas if discovery returned no area IDs."""
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.states.get.return_value = MagicMock(state="unavailable")
    entry = MagicMock()
    entry.entry_id = "spc-entry"
    entry.unique_id = "SPC12345678"
    coordinator = MagicMock()
    coordinator.async_restore_panel_tamper = AsyncMock()
    coordinator.async_restore_area_history = AsyncMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.data.panel.serial_number = "SPC12345678"
    coordinator._discovery_complete = True
    coordinator._detected_zone_ids = {1}
    coordinator._detected_area_ids = set()
    registry = MagicMock()
    with (
        patch(
            "custom_components.spc_flexc.SpcFlexCMappingGateCoordinator",
            return_value=coordinator,
        ),
        patch("custom_components.spc_flexc.er.async_get", return_value=registry),
        patch(
            "custom_components.spc_flexc.er.async_entries_for_config_entry",
            return_value=[
                MagicMock(
                    entity_id="alarm_control_panel.test",
                    unique_id="spc-entry_area_13",
                )
            ],
        ),
    ):
        assert await async_setup_entry(hass, entry)
        coordinator.async_add_listener.call_args.args[0]()
        registry.async_remove.assert_not_called()


@pytest.mark.asyncio
async def test_orphan_area_device_cleanup_removes_empty_device() -> None:
    """Remove an undiscovered area device once its entity registry is empty."""
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    entry = MagicMock(entry_id="spc-entry", unique_id="SPC12345678")
    coordinator = MagicMock()
    coordinator.async_restore_panel_tamper = AsyncMock()
    coordinator.async_restore_area_history = AsyncMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.data.panel.serial_number = "SPC12345678"
    coordinator._discovery_complete = True
    coordinator._detected_zone_ids = {1}
    coordinator._detected_area_ids = {1}
    registry = MagicMock()
    device_registry = MagicMock()
    orphan = MagicMock(
        id="device-3",
        identifiers={("spc_flexc", "SPC12345678_area_3")},
        config_entries={"spc-entry"},
    )
    device_registry.devices = {"device-3": orphan}
    orphan.via_device_id = None
    with (
        patch(
            "custom_components.spc_flexc.SpcFlexCMappingGateCoordinator",
            return_value=coordinator,
        ),
        patch("custom_components.spc_flexc.er.async_get", return_value=registry),
        patch(
            "custom_components.spc_flexc.er.async_entries_for_config_entry",
            return_value=[],
        ),
        patch(
            "custom_components.spc_flexc.er.async_entries_for_device", return_value=[]
        ),
        patch("custom_components.spc_flexc.dr.async_get", return_value=device_registry),
        patch(
            "custom_components.spc_flexc.dr.async_entries_for_config_entry",
            return_value=[orphan],
        ),
    ):
        assert await async_setup_entry(hass, entry)
        coordinator.async_add_listener.call_args.args[0]()
        device_registry.async_remove_device.assert_called_once_with("device-3")


@pytest.mark.asyncio
async def test_orphan_area_device_cleanup_keeps_device_with_entities() -> None:
    """Never delete an area device while any entity remains registered."""
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    entry = MagicMock(entry_id="spc-entry", unique_id="SPC12345678")
    coordinator = MagicMock()
    coordinator.async_restore_panel_tamper = AsyncMock()
    coordinator.async_restore_area_history = AsyncMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.data.panel.serial_number = "SPC12345678"
    coordinator._discovery_complete = True
    coordinator._detected_zone_ids = {1}
    coordinator._detected_area_ids = {1}
    device_registry = MagicMock()
    orphan = MagicMock(
        id="device-3",
        identifiers={("spc_flexc", "SPC12345678_area_3")},
        config_entries={"spc-entry"},
    )
    with (
        patch(
            "custom_components.spc_flexc.SpcFlexCMappingGateCoordinator",
            return_value=coordinator,
        ),
        patch("custom_components.spc_flexc.er.async_get"),
        patch(
            "custom_components.spc_flexc.er.async_entries_for_config_entry",
            return_value=[],
        ),
        patch(
            "custom_components.spc_flexc.er.async_entries_for_device",
            return_value=[MagicMock(device_id="device-3")],
        ),
        patch("custom_components.spc_flexc.dr.async_get", return_value=device_registry),
        patch(
            "custom_components.spc_flexc.dr.async_entries_for_config_entry",
            return_value=[orphan],
        ),
    ):
        assert await async_setup_entry(hass, entry)
        coordinator.async_add_listener.call_args.args[0]()
        device_registry.async_remove_device.assert_not_called()
