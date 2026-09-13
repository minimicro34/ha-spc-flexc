"""Tests for the SPC FlexC data update coordinator."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from custom_components.spc_flexc.coordinator import (
    ZONE_POLL_BATCH_SIZE,
    SpcFlexCCoordinator,
    _xbus_device_state_from_status,
    poll_delay_for_phase,
)
from custom_components.spc_flexc.models import SpcState, XBusDeviceState, ZoneState


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
    """Test large zone sets are split into bounded FlexC requests."""
    coordinator = MagicMock()
    coordinator.state = SpcState()
    coordinator._zone_discovery_complete = True
    coordinator._detected_zone_ids = set(range(1, 34))
    coordinator._discovery_requested = False
    coordinator._client_operation_lock = _AsyncLock()
    coordinator.client.async_ensure_connected = AsyncMock()
    coordinator.client.async_get_zone_status = AsyncMock(
        side_effect=[
            [{"ZONE_ID": str(zone_id)} for zone_id in range(1, 17)],
            [{"ZONE_ID": str(zone_id)} for zone_id in range(17, 33)],
            [{"ZONE_ID": "33"}],
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

    assert ZONE_POLL_BATCH_SIZE == 16
    assert coordinator.client.async_get_zone_status.await_args_list == [
        call(list(range(1, 17))),
        call(list(range(17, 33))),
        call([33]),
    ]
    assert set(coordinator.state.zones) == set(range(1, 34))


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


def test_xbus_status_mapping_preserves_raw_and_event_state() -> None:
    """Map validated ENETNODE metadata without guessing raw bit semantics."""
    previous = XBusDeviceState(
        device_id=1,
        sia_address=7,
        tamper_fault=True,
        tamper_isolated=True,
        last_event={"EV_ID": "5316"},
    )
    raw = {
        "ID": "1",
        "SN": "4CADF0DA",
        "NAME": "CLA 1",
        "TYPE": "1",
        "HARDWARE_ID": "1",
        "ICOUNT": "0",
        "OCOUNT": "0",
        "VERSION": "2.09 13MAR13",
        "RF_TYPE": "0",
        "RF_VERSION": "0",
        "READER_TYPE": "0",
        "STATUS": "00000004",
        "POSITION_1": "1",
        "POSITION_2": "0",
        "PSU_TYPE": "0",
        "AUX_VOLT": "13.7V",
        "AUX_CURR": "0mA",
        "INPUT": "0002",
        "ALERT": "0000",
        "INHIBIT": "0000",
        "ISOLATE": "0002",
    }

    device = _xbus_device_state_from_status(raw, previous)

    assert device is not None
    assert device.device_id == 1
    assert device.name == "CLA 1"
    assert device.serial_number == "4CADF0DA"
    assert device.aux_voltage == pytest.approx(13.7)
    assert device.aux_current == pytest.approx(0.0)
    assert device.status_raw == "00000004"
    assert device.input_raw == "0002"
    assert device.isolate_raw == "0002"
    assert device.sia_address == 7
    assert device.tamper_fault is True
    assert device.tamper_isolated is True
    assert device.last_event == {"EV_ID": "5316"}
    assert device.raw == raw


@pytest.mark.asyncio
async def test_xbus_polling_reconciles_raw_status_and_preserves_events() -> None:
    """Periodic STATUS_XBUS refreshes inventory without overwriting event state."""
    coordinator = MagicMock()
    coordinator.state = SpcState()
    coordinator.state.xbus_devices[1] = XBusDeviceState(
        device_id=1,
        name="CLA 1",
        tamper_fault=True,
        tamper_isolated=True,
        last_event={"EV_ID": "5316"},
        raw={"ID": "1", "INPUT": "0000"},
    )
    coordinator._xbus_discovery_complete = True
    coordinator._detected_xbus_ids = {1}
    coordinator._discovery_requested = False
    coordinator._client_operation_lock = _AsyncLock()
    coordinator.client.async_ensure_connected = AsyncMock()
    coordinator.async_set_updated_data = MagicMock()
    coordinator._xbus_poll_task = asyncio.current_task()
    sleep = AsyncMock(side_effect=[None, asyncio.CancelledError()])
    read_xbus = AsyncMock(
        return_value=[
            {
                "ID": "1",
                "NAME": "CLA 1",
                "STATUS": "00000004",
                "INPUT": "0002",
                "ISOLATE": "0002",
            }
        ]
    )

    with (
        patch("custom_components.spc_flexc.coordinator.asyncio.sleep", sleep),
        patch(
            "custom_components.spc_flexc.coordinator.async_get_xbus_status",
            read_xbus,
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await SpcFlexCCoordinator._async_xbus_poll_loop(coordinator)

    device = coordinator.state.xbus_devices[1]
    assert device.status_raw == "00000004"
    assert device.input_raw == "0002"
    assert device.isolate_raw == "0002"
    assert device.tamper_fault is True
    assert device.tamper_isolated is True
    assert device.last_event == {"EV_ID": "5316"}
    coordinator.async_set_updated_data.assert_called_once_with(coordinator.state)
    assert coordinator._xbus_poll_task is None
