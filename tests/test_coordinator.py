"""Tests for the SPC FlexC data update coordinator."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, call, patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.spc_flexc.coordinator import (
    ZONE_POLL_BATCH_SIZE,
    SpcFlexCCoordinator,
    _area_state_from_status,
    _ats_state_from_status,
    _bool_value,
    _door_state_from_status,
    _float_value,
    _int_value,
    _panel_state_from_summary,
    _spc_datetime,
    _xbus_device_state_from_status,
    _zone_state_from_status,
    poll_delay_for_phase,
)
from custom_components.spc_flexc.flexc.connection import FlexCConnectionError
from custom_components.spc_flexc.flexc.flexml import FlexMLError
from custom_components.spc_flexc.models import SpcState, XBusDeviceState, ZoneState


class _AsyncLock:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


def _coordinator_stub() -> MagicMock:
    coordinator = MagicMock()
    coordinator.state = SpcState()
    coordinator.hass.config.time_zone = "Europe/Paris"
    coordinator._client_operation_lock = _AsyncLock()
    coordinator._detected_ats_ids = set()
    coordinator._detected_area_ids = set()
    coordinator._detected_zone_ids = set()
    coordinator._detected_door_ids = set()
    coordinator._detected_xbus_serials = set()
    coordinator._ats_discovery_complete = False
    coordinator._area_discovery_complete = False
    coordinator._zone_discovery_complete = False
    coordinator._door_discovery_complete = False
    coordinator._xbus_discovery_complete = False
    coordinator._discovery_requested = False
    coordinator._discovery_task = None
    coordinator._zone_poll_task = None
    coordinator._xbus_poll_task = None
    coordinator.client.async_ensure_connected = AsyncMock()
    return coordinator


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


def test_coordinator_value_helpers_reject_invalid_values() -> None:
    """Protocol conversion helpers preserve unknown and malformed values."""
    assert _float_value(None) is None
    assert _float_value(" 13.7V ", "V") == pytest.approx(13.7)
    assert _float_value("bad") is None
    assert _int_value(None) is None
    assert _int_value(" 42 ") == 42
    assert _int_value("bad") is None
    assert _bool_value(None) is None
    assert _bool_value("0") is False
    assert _bool_value("1") is True
    assert _bool_value("2") is None

    timezone = ZoneInfo("Europe/Paris")
    assert _spc_datetime(None, timezone) is None
    parsed = _spc_datetime("12345617092026", timezone)
    assert parsed == datetime(2026, 9, 17, 12, 34, 56, tzinfo=timezone)
    assert _spc_datetime("invalid", timezone) is None


def test_protocol_status_mappers() -> None:
    """Panel, ATS, area, zone and door replies map documented fields."""
    timezone = ZoneInfo("Europe/Paris")

    panel = _panel_state_from_summary(
        {
            "SPC_BATT_VOLT": "13.5V",
            "SPC_AUX_VOLT": "13.7V",
            "SPC_AUX_CURR": "120mA",
            "SPC_AC_FREQ": "50Hz",
            "SPC_RF_TYPE": "2",
            "SPC_RF_VERSION": "1.0",
            "INTERNAL_BELLS": "1",
            "EXTERNAL_BELLS": "0",
            "ENG_MODE": "1",
            "INSTALLATION_NAME": "Home",
            "SPC_TYPE": "SPC4300",
            "SPC_VARIANT": "A",
            "SPC_SERIAL_NO": "1234",
            "SPC_FW_VERSION": "3.16.1",
            "SPC_HW_VERSION": "1",
        }
    )
    assert panel.battery_voltage == pytest.approx(13.5)
    assert panel.aux_current == pytest.approx(120.0)
    assert panel.ac_frequency == pytest.approx(50.0)
    assert panel.internal_bells is True
    assert panel.external_bells is False
    assert panel.installation_name == "Home"

    ats = _ats_state_from_status(
        {
            "ats": {
                "ATS_ID": "2",
                "ATS_NAME": "FlexC",
                "REGISTRATION_ID": "redacted",
                "ATS_STATUS": "1",
                "ATS_STATE": "2",
                "EVENT_LOG_COUNT": "3",
            },
            "atps": [
                {
                    "ATP_ID": "1",
                    "ATP_NAME": "Primary",
                    "ATP_UID": "7",
                    "ATP_STATUS": "1",
                    "ATP_STATE": "2",
                    "ATP_CONNECT_STATE": "3",
                    "LAST_TX_OK_TIMESTAMP": "12345617092026",
                }
            ],
        },
        timezone,
    )
    assert ats.ats_id == 2
    assert ats.status == 1
    assert ats.atps[1].connect_state == 3
    assert ats.atps[1].last_tx_ok_timestamp is not None

    area = _area_state_from_status(
        {
            "AREA_ID": "1",
            "AREA_NAME": "Home",
            "MODE": "0",
            "PARTSETA_ENABLE": "1",
            "PARTSETB_ENABLE": "0",
            "LAST_SET_TIME": "12345617092026",
            "LAST_SET_USER_ID": "5",
            "LAST_SET_USER_NAME": "nicolas",
            "LAST_UNSET_TIME": "11345617092026",
            "LAST_UNSET_USER_ID": "5",
            "LAST_UNSET_USER_NAME": "nicolas",
            "LAST_ALARM": "10345617092026",
            "INTERNAL_BELLS": "1",
            "EXTERNAL_BELLS": "0",
        },
        timezone,
    )
    assert area.area_id == 1
    assert area.partset_a_enabled is True
    assert area.partset_b_enabled is False
    assert area.last_set_user_id == 5

    zone = _zone_state_from_status(
        {
            "ZONE_ID": "4",
            "ZONE_NAME": "TV",
            "AREA_ID": "1",
            "AREA_NAME": "Home",
            "TYPE": "0",
            "INPUT": "1",
            "LOGIC_INPUT": "1",
            "STATUS": "2",
            "PROC_STATE": "0",
            "ALARM_STATE": "0",
            "INHIBIT_ALLOWED": "1",
            "ISOLATE_ALLOWED": "0",
            "ACTUATIONS_SINCE_LAST_READ": "3",
        }
    )
    assert zone.zone_id == 4
    assert zone.input_state == 1
    assert zone.inhibit_allowed is True
    assert zone.isolate_allowed is False
    assert zone.actuations_since_last_read == 3

    door = _door_state_from_status({"DOOR_ID": "2", "NAME": "Garage", "MODE": "7"})
    assert door.door_id == 2
    assert door.name == "Garage"
    assert door.mode == 7


def test_handle_flexc_event() -> None:
    """Test applying a FlexC EVENT to coordinator state."""
    coordinator = MagicMock(spec=SpcFlexCCoordinator)
    coordinator.state = SpcState()

    SpcFlexCCoordinator._handle_flexc_event(coordinator, {"EV_ID": "5336"})

    assert coordinator.state.faults.rf_jamming is True
    coordinator.async_set_updated_data.assert_called_once_with(coordinator.state)


def test_handle_flexc_restore_event() -> None:
    """Test restoring a fault through FlexC EVENT."""
    coordinator = MagicMock(spec=SpcFlexCCoordinator)
    coordinator.state = SpcState()
    coordinator.state.faults.xbus_mains_fault = True

    SpcFlexCCoordinator._handle_flexc_event(coordinator, {"EV_ID": "5325"})

    assert coordinator.state.faults.xbus_mains_fault is False
    coordinator.async_set_updated_data.assert_called_once_with(coordinator.state)


def test_unknown_flexc_event_does_not_notify() -> None:
    """Test unrelated EVENT does not trigger coordinator update."""
    coordinator = MagicMock(spec=SpcFlexCCoordinator)
    coordinator.state = SpcState()

    SpcFlexCCoordinator._handle_flexc_event(coordinator, {"EV_ID": "9999"})

    coordinator.async_set_updated_data.assert_not_called()


@pytest.mark.asyncio
async def test_update_data_refreshes_discovered_panel_objects() -> None:
    """Regular refresh updates panel, ATS and areas already found by discovery."""
    coordinator = _coordinator_stub()
    coordinator._ats_discovery_complete = True
    coordinator._detected_ats_ids = {2}
    coordinator._area_discovery_complete = True
    coordinator._detected_area_ids = {1}
    coordinator.client.async_get_panel_summary = AsyncMock(
        return_value={"INSTALLATION_NAME": "Home", "SPC_BATT_VOLT": "13.5V"}
    )
    coordinator.client.async_get_alert_status = AsyncMock(return_value=[])
    coordinator.client.async_get_flexc_ats_status = AsyncMock(
        return_value={"ats": {"ATS_ID": "2", "ATS_NAME": "FlexC"}, "atps": []}
    )
    coordinator.client.async_get_area_status = AsyncMock(
        return_value=[{"AREA_ID": "1", "AREA_NAME": "Home", "MODE": "0"}]
    )

    state = await SpcFlexCCoordinator._async_update_data(coordinator)

    assert state is coordinator.state
    assert state.panel.installation_name == "Home"
    assert state.ats[2].name == "FlexC"
    assert state.areas[1].name == "Home"
    assert state.faults.rf_jamming is False


@pytest.mark.asyncio
async def test_update_data_ignores_unavailable_detected_ats_and_reschedules() -> None:
    """A previously detected unavailable ATS does not abort the panel refresh."""
    coordinator = _coordinator_stub()
    coordinator._ats_discovery_complete = True
    coordinator._detected_ats_ids = {2}
    coordinator._discovery_requested = True
    coordinator._discovery_complete = False
    coordinator._schedule_discovery = MagicMock()
    coordinator.client.async_get_panel_summary = AsyncMock(return_value={})
    coordinator.client.async_get_alert_status = AsyncMock(return_value=[])
    coordinator.client.async_get_flexc_ats_status = AsyncMock(
        side_effect=FlexMLError("unavailable")
    )

    await SpcFlexCCoordinator._async_update_data(coordinator)

    coordinator._schedule_discovery.assert_called_once_with()


@pytest.mark.asyncio
async def test_update_data_wraps_transport_failure() -> None:
    """Transport failures surface to Home Assistant as UpdateFailed."""
    coordinator = _coordinator_stub()
    coordinator.client.async_ensure_connected = AsyncMock(
        side_effect=FlexCConnectionError("offline")
    )

    with pytest.raises(UpdateFailed, match="FlexC update failed"):
        await SpcFlexCCoordinator._async_update_data(coordinator)


@pytest.mark.asyncio
async def test_background_discovery_populates_all_object_families() -> None:
    """Background discovery records ATS, areas, zones, doors and X-BUS inventory."""
    coordinator = _coordinator_stub()
    coordinator._discovery_task = asyncio.current_task()
    coordinator.async_set_updated_data = MagicMock()
    coordinator._schedule_zone_polling = MagicMock()
    coordinator._schedule_xbus_polling = MagicMock()
    coordinator.client.async_get_flexc_ats_status = AsyncMock(
        side_effect=[
            FlexMLError("not present"),
            {"ats": {"ATS_ID": "2", "ATS_NAME": "FlexC"}, "atps": []},
        ]
    )
    areas = AsyncMock(return_value=[{"AREA_ID": "1", "AREA_NAME": "Home"}])
    zones = AsyncMock(return_value=[{"ZONE_ID": "4", "ZONE_NAME": "TV"}])
    doors = AsyncMock(return_value=[{"DOOR_ID": "2", "NAME": "Garage"}])
    xbus = AsyncMock(
        return_value=[
            {"ID": "1", "SN": "4CADF0DA", "NAME": "CLA 1", "TYPE": "1"},
            {"NAME": "invalid"},
        ]
    )

    with (
        patch("custom_components.spc_flexc.coordinator.ATS_IDS", (1, 2)),
        patch("custom_components.spc_flexc.coordinator.async_discover_areas", areas),
        patch("custom_components.spc_flexc.coordinator.async_discover_zones", zones),
        patch("custom_components.spc_flexc.coordinator.async_discover_doors", doors),
        patch("custom_components.spc_flexc.coordinator.async_get_xbus_status", xbus),
    ):
        await SpcFlexCCoordinator._async_discover_panel_objects(coordinator)

    assert coordinator._detected_ats_ids == {2}
    assert coordinator._detected_area_ids == {1}
    assert coordinator._detected_zone_ids == {4}
    assert coordinator._detected_door_ids == {2}
    assert coordinator._detected_xbus_serials == {"4CADF0DA"}
    assert coordinator._ats_discovery_complete is True
    assert coordinator._area_discovery_complete is True
    assert coordinator._zone_discovery_complete is True
    assert coordinator._door_discovery_complete is True
    assert coordinator._xbus_discovery_complete is True
    assert coordinator._discovery_task is None
    coordinator.async_set_updated_data.assert_called_once_with(coordinator.state)
    coordinator._schedule_zone_polling.assert_called_once_with()
    coordinator._schedule_xbus_polling.assert_called_once_with()


@pytest.mark.asyncio
async def test_xbus_discovery_preserves_duplicate_branch_local_ids() -> None:
    """Twelve ENETNODEs remain distinct when branch-local IDs are reused."""
    coordinator = _coordinator_stub()
    coordinator._discovery_task = asyncio.current_task()
    coordinator.async_set_updated_data = MagicMock()
    coordinator._schedule_zone_polling = MagicMock()
    coordinator._schedule_xbus_polling = MagicMock()
    coordinator.client.async_get_flexc_ats_status = AsyncMock(
        side_effect=[FlexMLError("not present"), FlexMLError("not present")]
    )
    rows = [
        (1, "1139A083", 1, "SPCE650 ID 1 LT"), (7, "12953F1B", 2, "SPCE650 ID 7 Gar"),
        (5, "10FFED63", 3, "SPCE650 ID 6 Gar"), (2, "0D9CC533", 4, "Garage"),
        (3, "10308F73", 5, "Studio"), (6, "10CE234B", 6, "SPCE650 ID 6 CG"),
        (9, "1D1F3A4A", 7, "SPCE450 ID 9 Gar"), (1, "4C28EE12", 8, "SPCA210 ID 1 Gar"),
        (8, "11D250C3", 9, "SPCE450 ID 8 Gar"), (2, "04F420A3", 10, "SPCE450 ID 2 LT"),
        (3, "02CB67CB", 11, "SPCE650 ID 3 PE"), (1, "06299D7B", 12, "Maison"),
    ]
    xbus = AsyncMock(return_value=[
        {"ID": str(device_id), "SN": serial, "POSITION_1": str(position), "NAME": name}
        for device_id, serial, position, name in rows
    ])

    with (
        patch("custom_components.spc_flexc.coordinator.ATS_IDS", (1, 2)),
        patch("custom_components.spc_flexc.coordinator.async_discover_areas", AsyncMock(return_value=[])),
        patch("custom_components.spc_flexc.coordinator.async_discover_zones", AsyncMock(return_value=[])),
        patch("custom_components.spc_flexc.coordinator.async_discover_doors", AsyncMock(return_value=[])),
        patch("custom_components.spc_flexc.coordinator.async_get_xbus_status", xbus),
    ):
        await SpcFlexCCoordinator._async_discover_panel_objects(coordinator)

    assert len(coordinator.state.xbus_devices) == 12
    assert len(coordinator._detected_xbus_serials) == 12
    assert sum(device.device_id == 1 for device in coordinator.state.xbus_devices.values()) == 3
    assert {device.position_1 for device in coordinator.state.xbus_devices.values()} == set(range(1, 13))


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
        side_effect=[[{"INPUT": "0"}], [{"ZONE_ID": "1", "INPUT": "1"}]]
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
        zone_id=1, zone_type=0, logic_input=0, actuations_since_last_read=0
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


def test_xbus_status_mapping_rejects_missing_id() -> None:
    """Malformed ENETNODE replies without a numeric ID are ignored."""
    assert _xbus_device_state_from_status({"NAME": "broken"}) is None
    assert _xbus_device_state_from_status({"ID": "bad"}) is None


@pytest.mark.asyncio
async def test_xbus_polling_reconciles_raw_status_and_preserves_events() -> None:
    """Periodic STATUS_XBUS refreshes inventory without overwriting event state."""
    coordinator = MagicMock()
    coordinator.state = SpcState()
    coordinator.state.xbus_devices["4CADF0DA"] = XBusDeviceState(
        device_id=1,
        serial_number="4CADF0DA",
        name="CLA 1",
        tamper_fault=True,
        tamper_isolated=True,
        last_event={"EV_ID": "5316"},
        raw={"ID": "1", "INPUT": "0000"},
    )
    coordinator._xbus_discovery_complete = True
    coordinator._detected_xbus_serials = {"4CADF0DA"}
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
                "SN": "4CADF0DA",
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
            "custom_components.spc_flexc.coordinator.async_get_xbus_status", read_xbus
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await SpcFlexCCoordinator._async_xbus_poll_loop(coordinator)

    device = coordinator.state.xbus_devices["4CADF0DA"]
    assert device.status_raw == "00000004"
    assert device.input_raw == "0002"
    assert device.isolate_raw == "0002"
    assert device.tamper_fault is True
    assert device.tamper_isolated is True
    assert device.last_event == {"EV_ID": "5316"}
    coordinator.async_set_updated_data.assert_called_once_with(coordinator.state)
    assert coordinator._xbus_poll_task is None
