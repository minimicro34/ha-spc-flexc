"""Tests for the SPC FlexC data update coordinator."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from custom_components.spc_flexc.coordinator import (
    ZONE_POLL_BATCH_SIZE,
    SpcFlexCCoordinator,
    poll_delay_for_phase,
)
from custom_components.spc_flexc.models import SpcState, ZoneState


class _AsyncLock:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


def test_poll_delay_for_phase_uses_fixed_monotonic_slots() -> None:
    """Test poll phases stay anchored instead of accumulating work-time drift."""
    loop = MagicMock()
    loop.time.side_effect = [10.10, 10.10, 10.10, 110.91]

    with patch(
        "custom_components.spc_flexc.coordinator.asyncio.get_running_loop",
        return_value=loop,
    ):
        assert poll_delay_for_phase(0.0, 1.0) == pytest.approx(0.90)
        assert poll_delay_for_phase(1.0 / 3.0, 1.0) == pytest.approx(0.2333333333)
        assert poll_delay_for_phase(2.0 / 3.0, 1.0) == pytest.approx(0.5666666667)
        assert poll_delay_for_phase(0.0, 1.0) == pytest.approx(0.09)


def test_handle_flexc_event() -> None:
    """Test applying a FlexC EVENT to coordinator state."""
    coordinator = MagicMock(spec=SpcFlexCCoordinator)
    coordinator.state = SpcState()

    SpcFlexCCoordinator._handle_flexc_event(
        coordinator,
        {"EV_ID": "5336"},
    )

    assert coordinator.state.faults.rf_jamming is True
    coordinator.async_set_updated_data.assert_called_once_with(coordinator.state)


def test_handle_flexc_restore_event() -> None:
    """Test restoring a fault through FlexC EVENT."""
    coordinator = MagicMock(spec=SpcFlexCCoordinator)
    coordinator.state = SpcState()
    coordinator.state.faults.xbus_mains_fault = True

    SpcFlexCCoordinator._handle_flexc_event(
        coordinator,
        {"EV_ID": "5325"},
    )

    assert coordinator.state.faults.xbus_mains_fault is False
    coordinator.async_set_updated_data.assert_called_once_with(coordinator.state)


def test_unknown_flexc_event_does_not_notify() -> None:
    """Test unrelated EVENT does not trigger coordinator update."""
    coordinator = MagicMock(spec=SpcFlexCCoordinator)
    coordinator.state = SpcState()

    SpcFlexCCoordinator._handle_flexc_event(
        coordinator,
        {"EV_ID": "9999"},
    )

    coordinator.async_set_updated_data.assert_not_called()


@pytest.mark.asyncio
async def test_zone_polling_continues_after_malformed_reply() -> None:
    """Test one malformed zone reply cannot permanently stop live polling."""
    coordinator = MagicMock()
    coordinator.state = SpcState()
    coordinator._zone_discovery_complete = True
    coordinator._detected_zone_ids = {1}
    coordinator._discovery_requested = False
    coordinator._client_operation_lock = _AsyncLock()
    coordinator.client.async_ensure_connected = AsyncMock()
    coordinator.client.async_get_zone_status = AsyncMock(
        side_effect=[
            [{"INPUT": "0"}],
            [{"ZONE_ID": "1", "INPUT": "1"}],
        ]
    )
    coordinator.async_set_updated_data = MagicMock()
    coordinator._zone_poll_task = asyncio.current_task()
    sleep = AsyncMock(side_effect=[None, None, asyncio.CancelledError()])

    with (
        patch("custom_components.spc_flexc.coordinator.asyncio.sleep", sleep),
        pytest.raises(asyncio.CancelledError),
    ):
        await SpcFlexCCoordinator._async_zone_poll_loop(coordinator)

    assert coordinator.client.async_get_zone_status.await_count == 2
    assert coordinator.state.zones[1].input_state == 1
    coordinator.async_set_updated_data.assert_called_once_with(coordinator.state)
    assert coordinator._zone_poll_task is None


@pytest.mark.asyncio
async def test_zone_actuation_change_notifies_entities() -> None:
    """Test a missed short activation still produces a coordinator update."""
    coordinator = MagicMock()
    coordinator.state = SpcState()
    coordinator.state.zones[1] = ZoneState(
        zone_id=1,
        zone_type=0,
        logic_input=0,
        actuations_since_last_read=0,
    )
    coordinator._zone_discovery_complete = True
    coordinator._detected_zone_ids = {1}
    coordinator._discovery_requested = False
    coordinator._client_operation_lock = _AsyncLock()
    coordinator.client.async_ensure_connected = AsyncMock()
    coordinator.client.async_get_zone_status = AsyncMock(
        return_value=[
            {
                "ZONE_ID": "1",
                "TYPE": "0",
                "LOGIC_INPUT": "0",
                "ACTUATIONS_SINCE_LAST_READ": "3",
            }
        ]
    )
    coordinator.async_set_updated_data = MagicMock()
    coordinator._zone_poll_task = asyncio.current_task()
    sleep = AsyncMock(side_effect=[None, asyncio.CancelledError()])

    with (
        patch("custom_components.spc_flexc.coordinator.asyncio.sleep", sleep),
        pytest.raises(asyncio.CancelledError),
    ):
        await SpcFlexCCoordinator._async_zone_poll_loop(coordinator)

    assert coordinator.state.zones[1].logic_input == 0
    assert coordinator.state.zones[1].actuations_since_last_read == 3
    coordinator.async_set_updated_data.assert_called_once_with(coordinator.state)


@pytest.mark.asyncio
async def test_zone_polling_uses_bounded_batches() -> None:
    """Test large zone sets are split into small FlexC requests."""
    coordinator = MagicMock()
    coordinator.state = SpcState()
    coordinator._zone_discovery_complete = True
    coordinator._detected_zone_ids = set(range(1, 18))
    coordinator._discovery_requested = False
    coordinator._client_operation_lock = _AsyncLock()
    coordinator.client.async_ensure_connected = AsyncMock()
    coordinator.client.async_get_zone_status = AsyncMock(
        side_effect=[
            [{"ZONE_ID": str(zone_id)} for zone_id in range(1, 9)],
            [{"ZONE_ID": str(zone_id)} for zone_id in range(9, 17)],
            [{"ZONE_ID": "17"}],
        ]
    )
    coordinator.async_set_updated_data = MagicMock()
    coordinator._zone_poll_task = asyncio.current_task()
    sleep = AsyncMock(side_effect=[None, asyncio.CancelledError()])

    with (
        patch("custom_components.spc_flexc.coordinator.asyncio.sleep", sleep),
        pytest.raises(asyncio.CancelledError),
    ):
        await SpcFlexCCoordinator._async_zone_poll_loop(coordinator)

    assert ZONE_POLL_BATCH_SIZE == 8
    assert coordinator.client.async_get_zone_status.await_args_list == [
        call(list(range(1, 9))),
        call(list(range(9, 17))),
        call([17]),
    ]
    assert set(coordinator.state.zones) == set(range(1, 18))


@pytest.mark.asyncio
async def test_zone_polling_restarts_if_task_stops_unexpectedly() -> None:
    """Test an unexpectedly stopped zone polling task schedules a replacement."""
    coordinator = MagicMock()
    coordinator._discovery_requested = True
    coordinator._schedule_zone_polling = MagicMock()
    coordinator._zone_poll_task = asyncio.current_task()
    sleep = AsyncMock(side_effect=asyncio.CancelledError())

    with (
        patch("custom_components.spc_flexc.coordinator.asyncio.sleep", sleep),
        pytest.raises(asyncio.CancelledError),
    ):
        await SpcFlexCCoordinator._async_zone_poll_loop(coordinator)

    coordinator._schedule_zone_polling.assert_called_once_with()
