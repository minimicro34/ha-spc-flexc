"""Tests for SPC FlexC door action buttons."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.spc_flexc.button import (
    DOOR_BUTTONS,
    SpcDoorActionButton,
    SpcZoneRestoreButton,
    async_setup_entry,
)
from custom_components.spc_flexc.models import AreaState, DoorState, SpcState, ZoneState


def _coordinator() -> MagicMock:
    coordinator = MagicMock()
    coordinator.entry.entry_id = "test"
    coordinator.entry.data = {"host": "192.0.2.1"}
    coordinator.data = SpcState()
    coordinator.data.doors[3] = DoorState(door_id=3, name="Garage")
    return coordinator


@pytest.mark.asyncio
async def test_door_action_button_properties_and_press() -> None:
    coordinator = _coordinator()
    coordinator.async_control_door = AsyncMock()
    button = SpcDoorActionButton(coordinator, 3, DOOR_BUTTONS[0])

    assert button.available is True
    assert button.unique_id == "test_door_3_open_momentarily"

    await button.async_press()
    coordinator.async_control_door.assert_awaited_once_with(3, 5)

    del coordinator.data.doors[3]
    assert button.available is False


@pytest.mark.asyncio
async def test_zone_restore_button_properties_availability_and_press() -> None:
    coordinator = _coordinator()
    coordinator.data.areas[1] = AreaState(area_id=1, name="Logis")
    coordinator.data.zones[1] = ZoneState(
        zone_id=1, name="TV", area_id=1, restore_allowed=True
    )
    coordinator.async_restore_zone = AsyncMock()

    button = SpcZoneRestoreButton(coordinator, 1)

    assert button.available is True
    assert button.unique_id == "test_zone_1_restore"
    assert button.extra_state_attributes == {
        "zone_id": 1,
        "restore_allowed": True,
    }

    await button.async_press()
    coordinator.async_restore_zone.assert_awaited_once_with(1)

    coordinator.data.zones[1].restore_allowed = False
    assert button.available is False
    assert button.extra_state_attributes["restore_allowed"] is False

    del coordinator.data.zones[1]
    assert button.available is False
    assert button.extra_state_attributes["restore_allowed"] is None


def test_zone_restore_button_falls_back_to_panel_device() -> None:
    coordinator = _coordinator()
    coordinator.data.zones[2] = ZoneState(
        zone_id=2, name=None, area_id=None, restore_allowed=True
    )

    button = SpcZoneRestoreButton(coordinator, 2)

    assert button.unique_id == "test_zone_2_restore"
    assert button.available is True


@pytest.mark.asyncio
async def test_setup_adds_four_buttons_once_and_discovers_new_door() -> None:
    coordinator = _coordinator()
    entry = MagicMock()
    entry.runtime_data = coordinator
    listener: list[object] = []
    entry.async_on_unload = MagicMock()
    coordinator.async_add_listener.side_effect = lambda callback: (
        listener.append(callback) or MagicMock()
    )
    batches: list[list[SpcDoorActionButton]] = []

    await async_setup_entry(
        MagicMock(), entry, lambda entities: batches.append(list(entities))
    )

    assert len(batches) == 1
    assert len(batches[0]) == 4
    assert {entity.entity_description.action for entity in batches[0]} == {5, 6, 7, 8}
    assert len(listener) == 1

    listener[0]()
    assert len(batches) == 1

    coordinator.data.doors[4] = DoorState(door_id=4, name="Studio")
    listener[0]()
    assert len(batches) == 2
    assert len(batches[1]) == 4
    assert {entity.door_id for entity in batches[1]} == {4}
