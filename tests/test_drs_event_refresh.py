"""Event-driven door status refresh for FlexC DRS release (#3012)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.spc_flexc.coordinator import SpcFlexCCoordinator
from custom_components.spc_flexc.models import DoorState, SpcState
from custom_components.spc_flexc.zone_control_coordinator import (
    SpcFlexCZoneControlCoordinator,
)


def _coordinator() -> MagicMock:
    coordinator = MagicMock(spec=SpcFlexCZoneControlCoordinator)
    coordinator.state = SpcState()
    coordinator.state.doors = {
        1: DoorState(door_id=1, area_id=2, drs_input=1, raw={"DRS_INPUT": "1"}),
        2: DoorState(door_id=2, area_id=3, drs_input=1, raw={"DRS_INPUT": "1"}),
    }
    coordinator._detected_door_ids = {1, 2}
    coordinator._door_discovery_complete = True
    coordinator._door_event_refresh_task = None
    coordinator._pending_event_door_ids = set()
    coordinator._async_refresh_doors_after_event.side_effect = lambda: (
        SpcFlexCZoneControlCoordinator._async_refresh_doors_after_event(coordinator)
    )
    coordinator._async_read_doors = AsyncMock(
        return_value=[{"DOOR_ID": "1", "AREA_ID": "2", "DRS_INPUT": "0"}]
    )
    coordinator._update_door_states.side_effect = lambda raw: (
        SpcFlexCZoneControlCoordinator._update_door_states(coordinator, raw)
    )
    coordinator.entry.async_create_background_task.side_effect = (
        lambda hass, coro, **kwargs: asyncio.create_task(coro)
    )
    return coordinator


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("event", "expected"),
    [
        ({"EV_ID": "3012", "DOOR_ID": "1", "AREA_ID": "3"}, [1]),
        ({"EV_ID": "3012", "AREA_ID": "2"}, [1]),
        ({"EV_ID": "3012", "AREA_ID": "99"}, [1, 2]),
        ({"EV_ID": "3012"}, [1, 2]),
    ],
)
async def test_drs_event_refreshes_matching_doors(event, expected) -> None:
    coordinator = _coordinator()
    with patch.object(SpcFlexCCoordinator, "_handle_flexc_event"):
        SpcFlexCZoneControlCoordinator._handle_flexc_event(coordinator, event)
    await coordinator._door_event_refresh_task
    coordinator._async_read_doors.assert_awaited_once_with(expected)
    assert coordinator.state.doors[1].drs_input == 0
    coordinator.async_set_updated_data.assert_called_once_with(coordinator.state)


@pytest.mark.asyncio
async def test_non_drs_event_does_not_schedule_door_read() -> None:
    coordinator = _coordinator()
    with patch.object(SpcFlexCCoordinator, "_handle_flexc_event"):
        SpcFlexCZoneControlCoordinator._handle_flexc_event(
            coordinator, {"EV_ID": "3011", "DOOR_ID": "1"}
        )
    coordinator.entry.async_create_background_task.assert_not_called()


@pytest.mark.asyncio
async def test_drs_event_uses_discovered_doors_only() -> None:
    coordinator = _coordinator()
    with patch.object(SpcFlexCCoordinator, "_handle_flexc_event"):
        SpcFlexCZoneControlCoordinator._handle_flexc_event(
            coordinator, {"EV_ID": "3012", "DOOR_ID": "99", "AREA_ID": "2"}
        )
    await coordinator._door_event_refresh_task
    coordinator._async_read_doors.assert_awaited_once_with([1])
