"""Tests for persistent door-control recovery after FlexC timeouts."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.spc_flexc.flexc.connection import FlexCCommandTimeout
from custom_components.spc_flexc.models import DoorState, SpcState
from custom_components.spc_flexc.zone_control_coordinator import (
    SpcFlexCZoneControlCoordinator,
)


class AsyncMockContextManager:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


def _coordinator(responses: list[object]) -> MagicMock:
    coordinator = MagicMock(spec=SpcFlexCZoneControlCoordinator)
    coordinator.state = SpcState(doors={1: DoorState(door_id=1, name="Garage")})
    coordinator.client = MagicMock()
    coordinator.client.command_username = "user"
    coordinator.client.command_password = "password"
    coordinator.client.async_ensure_connected = AsyncMock()
    coordinator.client.async_recover_session = AsyncMock()
    coordinator.client.async_send_flexml = AsyncMock(side_effect=responses)
    coordinator._client_operation_lock = AsyncMockContextManager()
    coordinator.async_set_updated_data = MagicMock()
    coordinator._update_door_states = lambda raw: (
        SpcFlexCZoneControlCoordinator._update_door_states(coordinator, raw)
    )
    return coordinator


@pytest.mark.asyncio
@pytest.mark.parametrize(("action", "target_mode"), [(6, 2), (7, 0), (8, 1)])
async def test_timeout_does_not_replay_when_mode_already_matches(
    action: int, target_mode: int
) -> None:
    coordinator = _coordinator([FlexCCommandTimeout("timeout"), "status"])
    with (
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.build_door_control_command",
            return_value="control-cmd",
        ),
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.build_door_status_batch",
            return_value="status-cmd",
        ),
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.parse_door_status",
            return_value=[{"DOOR_ID": "1", "MODE": str(target_mode)}],
        ),
    ):
        await SpcFlexCZoneControlCoordinator.async_control_door(coordinator, 1, action)

    assert coordinator.client.async_send_flexml.await_count == 2


@pytest.mark.asyncio
async def test_timeout_replays_persistent_action_once_and_verifies() -> None:
    coordinator = _coordinator(
        [FlexCCommandTimeout("timeout"), "status-1", "control-2", "status-2"]
    )
    with (
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.build_door_control_command",
            return_value="control-cmd",
        ),
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.parse_door_control",
        ),
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.build_door_status_batch",
            return_value="status-cmd",
        ),
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.parse_door_status",
            side_effect=[
                [{"DOOR_ID": "1", "MODE": "0"}],
                [{"DOOR_ID": "1", "MODE": "1"}],
            ],
        ),
    ):
        await SpcFlexCZoneControlCoordinator.async_control_door(coordinator, 1, 8)

    assert coordinator.client.async_send_flexml.await_count == 4
    assert coordinator.client.async_send_flexml.await_args_list[2].args == ("control-cmd",)
    assert coordinator.state.doors[1].mode == 1


@pytest.mark.asyncio
async def test_timeout_does_not_replay_unknown_mode() -> None:
    coordinator = _coordinator([FlexCCommandTimeout("timeout"), "status"])
    with (
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.build_door_control_command",
            return_value="control-cmd",
        ),
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.build_door_status_batch",
            return_value="status-cmd",
        ),
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.parse_door_status",
            return_value=[{"DOOR_ID": "1", "MODE": "9"}],
        ),
        pytest.raises(ValueError, match="mode is unknown"),
    ):
        await SpcFlexCZoneControlCoordinator.async_control_door(coordinator, 1, 8)

    assert coordinator.client.async_send_flexml.await_count == 2
