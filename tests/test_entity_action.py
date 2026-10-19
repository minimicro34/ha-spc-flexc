"""Regression tests for SPC entity action error handling."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.spc_flexc.button import DOOR_BUTTONS, SpcDoorActionButton
from custom_components.spc_flexc.entity_action import async_entity_action
from custom_components.spc_flexc.flexc.connection import FlexCError
from custom_components.spc_flexc.flexc.flexml import FlexMLError
from custom_components.spc_flexc.models import DoorState, SpcState, ZoneState
from custom_components.spc_flexc.switch import SpcZoneInhibitionSwitch


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (ValueError("inhibition not allowed"), ServiceValidationError),
        (FlexCError("connection lost"), HomeAssistantError),
        (FlexMLError("invalid reply"), HomeAssistantError),
    ],
)
async def test_entity_action_maps_expected_errors(failure, expected) -> None:
    async def fail():
        raise failure

    with pytest.raises(expected):
        await async_entity_action(fail())


@pytest.mark.asyncio
async def test_entity_action_preserves_unexpected_errors() -> None:
    async def fail():
        raise RuntimeError("programming error")

    with pytest.raises(RuntimeError, match="programming error"):
        await async_entity_action(fail())


@pytest.mark.asyncio
async def test_door_button_exposes_validation_failure() -> None:
    coordinator = MagicMock()
    coordinator.entry.entry_id = "test"
    coordinator.entry.data = {"host": "192.0.2.1"}
    coordinator.data = SpcState()
    coordinator.data.doors[3] = DoorState(door_id=3, name="Garage")
    coordinator.async_control_door = AsyncMock(
        side_effect=ValueError("door action denied")
    )
    button = SpcDoorActionButton(coordinator, 3, DOOR_BUTTONS[0])

    with pytest.raises(ServiceValidationError, match="door action denied"):
        await button.async_press()


@pytest.mark.asyncio
async def test_mapping_gate_switch_exposes_connection_failure() -> None:
    coordinator = MagicMock()
    coordinator.entry.entry_id = "test"
    coordinator.entry.data = {"host": "192.0.2.1"}
    coordinator.data = SpcState()
    coordinator.data.zones[1] = ZoneState(zone_id=1, name="PIR")
    coordinator.async_inhibit_zone = AsyncMock(side_effect=FlexCError("disconnected"))
    entity = SpcZoneInhibitionSwitch(coordinator, 1)

    with pytest.raises(HomeAssistantError, match="SPC communication failed"):
        await entity.async_turn_on()
