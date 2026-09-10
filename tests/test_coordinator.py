"""Tests for the SPC FlexC data update coordinator."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.spc_flexc.coordinator import (
    SpcFlexCCoordinator,
)
from custom_components.spc_flexc.models import SpcState


class _AsyncLock:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


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


def test_zone_polling_continues_after_malformed_reply() -> None:
    """Test one malformed zone reply cannot permanently stop live polling."""
    coordinator = MagicMock()
    coordinator.state = SpcState()
    coordinator._zone_discovery_complete = True
    coordinator._detected_zone_ids = {1}
    coordinator._client_operation_lock = _AsyncLock()
    coordinator.client.async_ensure_connected = AsyncMock()
    coordinator.client.async_get_zone_status = AsyncMock(
        side_effect=[
            [{"INPUT": "0"}],
            [{"ZONE_ID": "1", "INPUT": "1"}],
        ]
    )
    coordinator.async_set_updated_data = MagicMock()

    async def _run() -> None:
        coordinator._zone_poll_task = asyncio.current_task()
        sleep = AsyncMock(side_effect=[None, None, asyncio.CancelledError()])
        with patch("custom_components.spc_flexc.coordinator.asyncio.sleep", sleep):
            try:
                await SpcFlexCCoordinator._async_zone_poll_loop(coordinator)
            except asyncio.CancelledError:
                pass

    asyncio.run(_run())

    assert coordinator.client.async_get_zone_status.await_count == 2
    assert coordinator.state.zones[1].input_state == 1
    coordinator.async_set_updated_data.assert_called_once_with(coordinator.state)
    assert coordinator._zone_poll_task is None
