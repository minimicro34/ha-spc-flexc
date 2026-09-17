"""Tests for SPC FlexC sensor entities."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from custom_components.spc_flexc.models import (
    AtpState,
    AtsState,
    DoorState,
    SpcState,
    XBusDeviceState,
)
from custom_components.spc_flexc.sensor import (
    DESCRIPTIONS,
    SpcAtpLastTxSensor,
    SpcAtsActivePathSensor,
    SpcDoorModeSensor,
    SpcDoorStatusSensor,
    SpcPanelSensor,
    SpcXBusAuxCurrentSensor,
    SpcXBusAuxVoltageSensor,
    SpcXBusDiagnosticSensor,
    SpcXBusInventorySensor,
    async_setup_entry,
    build_device_info,
)


def _coordinator() -> MagicMock:
    coordinator = MagicMock()
    coordinator.entry.entry_id = "test"
    coordinator.entry.data = {"host": "192.0.2.1"}
    coordinator.data = SpcState()
    panel = coordinator.data.panel
    panel.installation_name = "Maison"
    panel.serial_number = "SERIAL"
    panel.spc_variant = "4300"
    panel.firmware_version = "3.16.1"
    panel.hardware_version = "1"
    panel.battery_voltage = 13.7
    panel.aux_voltage = 13.6
    panel.aux_current = 120.0
    panel.ac_frequency = 50.0
    return coordinator


def test_panel_sensors_and_device_info() -> None:
    coordinator = _coordinator()
    sensors = [SpcPanelSensor(coordinator, description) for description in DESCRIPTIONS]
    assert [sensor.native_value for sensor in sensors] == [13.7, 13.6, 120.0, 50.0]
    info = build_device_info(coordinator)
    assert info["identifiers"] == {("spc_flexc", "SERIAL")}
    assert info["name"] == "Maison"
    assert info["model"] == "SPC4300"
    assert info["configuration_url"] == "http://192.0.2.1"
    coordinator.data.panel.serial_number = None
    coordinator.data.panel.installation_name = None
    coordinator.data.panel.spc_variant = None
    coordinator.data.panel.spc_type = "SPC"
    fallback = build_device_info(coordinator)
    assert fallback["serial_number"] == "test"
    assert fallback["name"] == "SPC"
    assert fallback["model"] == "SPC"


def test_ats_and_atp_sensors() -> None:
    coordinator = _coordinator()
    stamp = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    coordinator.data.ats[2] = AtsState(
        ats_id=2,
        name="FlexC",
        atps={
            1: AtpState(
                atp_id=1,
                name="Ethernet",
                connect_state=16,
                last_tx_ok_timestamp=stamp,
            ),
            2: AtpState(atp_id=2, name="Backup", connect_state=0),
        },
    )
    active = SpcAtsActivePathSensor(coordinator, 2)
    last_tx = SpcAtpLastTxSensor(coordinator, 2, 1)
    assert active.available is True
    assert active.native_value == "Ethernet"
    assert last_tx.available is True
    assert last_tx.native_value == stamp
    coordinator.data.ats[2].atps[1].name = None
    assert active.native_value == "ATP 1"
    coordinator.data.ats[2].atps[1].connect_state = 0
    assert active.native_value is None
    del coordinator.data.ats[2]
    assert active.available is False
    assert active.native_value is None
    assert last_tx.available is False
    assert last_tx.native_value is None


def test_door_sensors() -> None:
    coordinator = _coordinator()
    coordinator.data.doors[4] = DoorState(
        door_id=4,
        name="Garage",
        status=2,
        mode=3,
        zone_id=9,
        zone_name="Porte",
        area_id=1,
        area_name="Logis",
        area_side_1=1,
        area_side_1_name="Logis",
        dps_input=1,
        drs_input=0,
        reader1_format=2,
        reader2_format=3,
        entry_exit=True,
        normal_allowed=True,
        lock_allowed=False,
    )
    status = SpcDoorStatusSensor(coordinator, 4)
    mode = SpcDoorModeSensor(coordinator, 4)
    assert status.available is True
    assert status.native_value == 2
    assert mode.native_value == 3
    attrs = status.extra_state_attributes
    assert attrs["zone_id"] == 9
    assert attrs["entry_exit"] is True
    assert attrs["raw_status"] == 2
    del coordinator.data.doors[4]
    assert status.available is False
    assert status.native_value is None
    assert mode.native_value is None
    assert status.extra_state_attributes == {}


def test_xbus_sensors_and_diagnostics() -> None:
    coordinator = _coordinator()
    coordinator.data.xbus_devices[7] = XBusDeviceState(
        device_id=7,
        name="SPCE650",
        serial_number="XB7",
        device_type=2,
        hardware_id=1,
        input_count=8,
        output_count=2,
        version="1.0",
        aux_voltage=13.4,
        aux_current=85.0,
        status_raw="0004",
        input_raw="0002",
        alert_raw="0002",
        inhibit_raw="0000",
        isolate_raw="0000",
    )
    voltage = SpcXBusAuxVoltageSensor(coordinator, 7)
    current = SpcXBusAuxCurrentSensor(coordinator, 7)
    diagnostics = SpcXBusDiagnosticSensor(coordinator, 7)
    inputs = SpcXBusInventorySensor(coordinator, 7, "input_count")
    device_id = SpcXBusInventorySensor(coordinator, 7, "device_id", diagnostic=True)
    assert voltage.available is True
    assert voltage.native_value == 13.4
    assert current.native_value == 85.0
    assert diagnostics.native_value == "0004"
    assert diagnostics.extra_state_attributes["input_raw"] == "0002"
    assert inputs.native_value == 8
    assert device_id.native_value == 7
    del coordinator.data.xbus_devices[7]
    assert voltage.available is False
    assert voltage.native_value is None
    assert current.native_value is None
    assert diagnostics.native_value is None
    assert diagnostics.extra_state_attributes == {}
    assert inputs.native_value is None


@pytest.mark.asyncio
async def test_setup_entry_adds_static_and_dynamic_sensors() -> None:
    coordinator = _coordinator()
    coordinator.data.ats[1] = AtsState(ats_id=1, atps={1: AtpState(atp_id=1)})
    coordinator.data.doors[2] = DoorState(door_id=2)
    coordinator.data.xbus_devices[3] = XBusDeviceState(device_id=3, device_type=2)
    entry = MagicMock()
    entry.runtime_data = coordinator
    listeners: list[object] = []
    coordinator.async_add_listener.side_effect = (
        lambda callback: listeners.append(callback) or MagicMock()
    )
    batches: list[list[object]] = []
    await async_setup_entry(
        MagicMock(), entry, lambda entities: batches.append(list(entities))
    )
    assert len(batches[0]) == 4
    assert len(batches[1]) == 10
    assert len(listeners) == 1
    listeners[0]()
    assert len(batches) == 2
    coordinator.data.xbus_devices[4] = XBusDeviceState(device_id=4, device_type=7)
    listeners[0]()
    assert len(batches[2]) == 4
