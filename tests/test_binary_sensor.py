"""Tests for SPC FlexC binary sensors."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.spc_flexc.binary_sensor import (
    FAULTS,
    PANEL,
    ZONE_ACTIVITY_PULSE_SECONDS,
    SpcAtpFaultSensor,
    SpcBinary,
    SpcFlexCConnectionSensor,
    SpcXBusDeviceBinarySensor,
    SpcZoneBinarySensor,
    _xbus_mask_state,
    async_setup_entry,
    zone_device_class,
)
from custom_components.spc_flexc.models import (
    AreaState,
    AtpState,
    AtsState,
    SpcState,
    XBusDeviceState,
    ZoneState,
)


def _coordinator() -> MagicMock:
    coordinator = MagicMock()
    coordinator.entry.entry_id = "test"
    coordinator.entry.data = {"host": "192.0.2.1"}
    coordinator.data = SpcState()
    coordinator.last_update_success = True
    coordinator.client.connected = True
    return coordinator


def _zone_sensor(
    *,
    logic_input: int = 0,
    actuations: int = 0,
    zone_type: int = 0,
) -> tuple[SpcZoneBinarySensor, MagicMock]:
    coordinator = _coordinator()
    coordinator.data.zones[1] = ZoneState(
        zone_id=1,
        name="PIR",
        zone_type=zone_type,
        logic_input=logic_input,
        actuations_since_last_read=actuations,
    )
    sensor = SpcZoneBinarySensor(coordinator, 1)
    sensor.async_write_ha_state = MagicMock()
    return sensor, coordinator


def test_standard_panel_fault_and_connection_sensors() -> None:
    coordinator = _coordinator()
    coordinator.data.panel.internal_bells = True
    coordinator.data.faults.mains_fault = False

    panel = SpcBinary(coordinator, PANEL[0], "panel")
    fault = SpcBinary(coordinator, FAULTS[0], "faults")
    connection = SpcFlexCConnectionSensor(coordinator)

    assert panel.is_on is True
    assert fault.is_on is False
    assert fault._attr_device_class == BinarySensorDeviceClass.PROBLEM
    assert connection.is_on is True
    coordinator.client.connected = False
    assert connection.is_on is False


def test_atp_fault_sensor_state_and_availability() -> None:
    coordinator = _coordinator()
    coordinator.data.ats[2] = AtsState(
        ats_id=2,
        atps={1: AtpState(atp_id=1, name="Ethernet", status=2)},
    )
    sensor = SpcAtpFaultSensor(coordinator, 2, 1)

    assert sensor.available is True
    assert sensor.is_on is True
    coordinator.data.ats[2].atps[1].status = 1
    assert sensor.is_on is False
    del coordinator.data.ats[2].atps[1]
    assert sensor.available is False
    assert sensor.is_on is None
    del coordinator.data.ats[2]
    assert sensor.available is False
    assert sensor.is_on is None


def test_zone_device_classes() -> None:
    expected = {
        0: BinarySensorDeviceClass.MOTION,
        2: BinarySensorDeviceClass.MOTION,
        1: BinarySensorDeviceClass.OPENING,
        30: BinarySensorDeviceClass.OPENING,
        3: BinarySensorDeviceClass.SMOKE,
        4: BinarySensorDeviceClass.DOOR,
        8: BinarySensorDeviceClass.TAMPER,
        15: BinarySensorDeviceClass.PROBLEM,
        19: BinarySensorDeviceClass.PROBLEM,
        20: BinarySensorDeviceClass.PROBLEM,
        23: BinarySensorDeviceClass.VIBRATION,
        24: BinarySensorDeviceClass.MOISTURE,
        25: BinarySensorDeviceClass.HEAT,
        27: BinarySensorDeviceClass.GAS,
        29: BinarySensorDeviceClass.GAS,
    }
    for zone_type, device_class in expected.items():
        assert zone_device_class(zone_type) == device_class
    assert zone_device_class(9) is None
    assert zone_device_class(None) is None


def test_zone_state_attributes_availability_and_parent_device() -> None:
    coordinator = _coordinator()
    coordinator.data.areas[1] = AreaState(area_id=1, name="Logis")
    coordinator.data.zones[1] = ZoneState(
        zone_id=1,
        name="PIR",
        area_id=1,
        zone_type=0,
        logic_input=1,
        status=2,
        proc_state=3,
        alarm_state=4,
        event_tamper=True,
        actuations_since_last_read=2,
        raw={"INHIBITED": "1", "ISOLATED": "1"},
    )
    sensor = SpcZoneBinarySensor(coordinator, 1)

    assert sensor.is_on is True
    assert sensor.available is True
    attrs = sensor.extra_state_attributes
    assert attrs["spc_zone_type"] == "alarm"
    assert attrs["inhibited"] is True
    assert attrs["isolated"] is True
    assert attrs["event_tamper"] is True

    del coordinator.data.zones[1]
    assert sensor.is_on is None
    assert sensor.available is False
    assert sensor.extra_state_attributes == {}


def test_zone_without_area_uses_panel_device() -> None:
    coordinator = _coordinator()
    coordinator.data.zones[3] = ZoneState(zone_id=3, zone_type=9)
    sensor = SpcZoneBinarySensor(coordinator, 3)
    assert sensor._attr_device_info["identifiers"] == {("spc_flexc", "test")}


def test_missed_motion_starts_two_second_local_pulse() -> None:
    sensor, coordinator = _zone_sensor(logic_input=0, actuations=3)
    loop = MagicMock()
    handle = MagicMock()
    loop.call_later.return_value = handle

    with (
        patch(
            "custom_components.spc_flexc.binary_sensor.asyncio.get_running_loop",
            return_value=loop,
        ),
        patch.object(CoordinatorEntity, "_handle_coordinator_update"),
    ):
        sensor._handle_coordinator_update()

    assert sensor.is_on is True
    assert coordinator.data.zones[1].logic_input == 0
    loop.call_later.assert_called_once_with(
        ZONE_ACTIVITY_PULSE_SECONDS,
        sensor._end_activity_pulse,
    )


def test_new_actuation_restarts_existing_activity_pulse() -> None:
    sensor, _ = _zone_sensor(logic_input=0, actuations=1)
    loop = MagicMock()
    first_handle = MagicMock()
    second_handle = MagicMock()
    loop.call_later.side_effect = [first_handle, second_handle]

    with patch(
        "custom_components.spc_flexc.binary_sensor.asyncio.get_running_loop",
        return_value=loop,
    ):
        sensor._start_activity_pulse()
        sensor._start_activity_pulse()

    first_handle.cancel.assert_called_once_with()
    assert sensor._activity_pulse_handle is second_handle
    assert sensor.is_on is True


def test_activity_pulse_returns_to_raw_zone_state() -> None:
    sensor, coordinator = _zone_sensor(logic_input=0, actuations=1)
    sensor._activity_pulse_active = True
    sensor._activity_pulse_handle = MagicMock()

    sensor._end_activity_pulse()

    assert sensor.is_on is False
    assert coordinator.data.zones[1].logic_input == 0
    assert sensor._activity_pulse_handle is None
    sensor.async_write_ha_state.assert_called_once_with()


def test_actuation_pulse_is_limited_to_motion_zones() -> None:
    sensor, _ = _zone_sensor(logic_input=0, actuations=1, zone_type=4)
    with patch.object(CoordinatorEntity, "_handle_coordinator_update"):
        sensor._handle_coordinator_update()
    assert sensor.is_on is False
    assert sensor._activity_pulse_handle is None


@pytest.mark.asyncio
async def test_zone_removal_cancels_activity_timer() -> None:
    sensor, _ = _zone_sensor()
    handle = MagicMock()
    sensor._activity_pulse_handle = handle
    with patch.object(
        CoordinatorEntity, "async_will_remove_from_hass", new=AsyncMock()
    ) as parent_remove:
        await sensor.async_will_remove_from_hass()
    handle.cancel.assert_called_once_with()
    assert sensor._activity_pulse_handle is None
    parent_remove.assert_awaited_once_with()


def test_xbus_mask_and_tamper_sensors() -> None:
    assert _xbus_mask_state(None, 2) is None
    assert _xbus_mask_state("not-hex", 2) is None
    assert _xbus_mask_state("0000", 2) is False
    assert _xbus_mask_state("0002", 2) is True

    coordinator = _coordinator()
    coordinator.data.xbus_devices[1] = XBusDeviceState(
        device_id=1,
        name="CLA",
        serial_number="XB1",
        device_type=1,
        version="1.0",
        status_raw="0004",
        input_raw="0002",
        alert_raw="0002",
        inhibit_raw="0002",
        isolate_raw="0000",
    )
    fault = SpcXBusDeviceBinarySensor(coordinator, 1, "tamper_fault")
    inhibited = SpcXBusDeviceBinarySensor(coordinator, 1, "tamper_inhibited")
    isolated = SpcXBusDeviceBinarySensor(coordinator, 1, "tamper_isolated")

    assert fault.is_on is True
    assert inhibited.is_on is True
    assert isolated.is_on is False
    assert fault.available is True
    attrs = fault.extra_state_attributes
    assert attrs["input_raw"] == "0002"
    assert attrs["tamper_inhibited"] is True

    coordinator.data.xbus_devices[1].tamper_fault = False
    coordinator.data.xbus_devices[1].tamper_isolated = True
    assert fault.is_on is False
    assert isolated.is_on is True

    del coordinator.data.xbus_devices[1]
    assert fault.is_on is None
    assert fault.available is False
    assert fault.extra_state_attributes == {}


@pytest.mark.asyncio
async def test_setup_entry_adds_dynamic_binary_sensors_once() -> None:
    coordinator = _coordinator()
    coordinator.data.zones[1] = ZoneState(zone_id=1)
    coordinator.data.ats[1] = AtsState(ats_id=1, atps={1: AtpState(atp_id=1)})
    coordinator.data.xbus_devices[1] = XBusDeviceState(device_id=1)
    entry = MagicMock()
    entry.runtime_data = coordinator
    callbacks: list[object] = []
    coordinator.async_add_listener.side_effect = lambda callback: (
        callbacks.append(callback) or MagicMock()
    )
    batches: list[list[object]] = []

    await async_setup_entry(
        MagicMock(), entry, lambda entities: batches.append(list(entities))
    )

    assert len(batches[0]) == len(PANEL) + len(FAULTS) + 1
    assert [len(batch) for batch in batches[1:]] == [1, 1, 3]
    assert len(callbacks) == 1
    callbacks[0]()
    assert len(batches) == 4

    coordinator.data.zones[2] = ZoneState(zone_id=2)
    coordinator.data.ats[1].atps[2] = AtpState(atp_id=2)
    coordinator.data.xbus_devices[2] = XBusDeviceState(device_id=2)
    callbacks[0]()
    assert [len(batch) for batch in batches[4:]] == [1, 1, 3]
