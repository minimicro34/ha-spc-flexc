"""Tests for SPC FlexC Home Assistant device helpers."""

from unittest.mock import MagicMock, patch

from custom_components.spc_flexc.flexc.device import (
    _xbus_model,
    build_area_device_info,
    build_door_device_info,
    build_panel_device_info,
    build_xbus_device_info,
)
from custom_components.spc_flexc.models import AreaState, DoorState, SpcState, XBusDeviceState


def _coordinator() -> MagicMock:
    coordinator = MagicMock()
    coordinator.entry.entry_id = "entry"
    coordinator.entry.data = {"host": "192.0.2.1"}
    coordinator.data = SpcState()
    coordinator.data.panel.serial_number = "SERIAL"
    coordinator.data.panel.installation_name = "Maison"
    coordinator.data.panel.spc_variant = "4300"
    return coordinator


def test_xbus_model_validated_families() -> None:
    assert _xbus_model(1, 0, 0) == "SPC Keypad"
    assert _xbus_model(7, 0, 0) == "SPC Comfort Keypad"
    assert _xbus_model(6, 4, 2) == "SPCA210 2-door expander"
    assert _xbus_model(2, 8, 2).startswith("SPCE650")
    assert _xbus_model(2, 0, 8).startswith("SPCE450")
    assert _xbus_model(2, 4, 4) == "SPC I/O expander"
    assert _xbus_model(99, None, None) == "SPC X-BUS"


def test_panel_area_door_and_xbus_device_info() -> None:
    coordinator = _coordinator()
    coordinator.data.areas[1] = AreaState(area_id=1, name="Logis")
    coordinator.data.doors[2] = DoorState(door_id=2, name="Garage", area_id=1)
    coordinator.data.xbus_devices[3] = XBusDeviceState(
        device_id=3, name="Extension", device_type=2, input_count=8, output_count=2,
        serial_number="XB3", version="1.2",
    )

    with patch(
        "custom_components.spc_flexc.flexc.device.dr.async_get_device_id_by_identifier",
        return_value="parent-id",
        create=True,
    ):
        panel = build_panel_device_info(coordinator)
        area = build_area_device_info(coordinator, 1)
        door = build_door_device_info(coordinator, 2)
        xbus = build_xbus_device_info(coordinator, 3)

    assert panel["model"] == "SPC4300"
    assert area["name"] == "Logis"
    assert area["via_device_id"] == "parent-id"
    assert door["name"] == "Garage"
    assert door["via_device_id"] == "parent-id"
    assert xbus["model"].startswith("SPCE650")
    assert xbus["serial_number"] == "XB3"
    assert xbus["via_device_id"] == "parent-id"


def test_device_info_fallback_names_and_no_parent_helper() -> None:
    coordinator = _coordinator()
    coordinator.data.panel.serial_number = None
    coordinator.data.panel.installation_name = None
    coordinator.data.panel.spc_variant = None
    coordinator.data.panel.spc_type = None
    coordinator.data.areas[5] = AreaState(area_id=5)
    coordinator.data.doors[6] = DoorState(door_id=6, zone_name="Zone porte")
    coordinator.data.xbus_devices[7] = XBusDeviceState(device_id=7)

    with patch(
        "custom_components.spc_flexc.flexc.device.dr.async_get_device_id_by_identifier",
        None,
        create=True,
    ):
        panel = build_panel_device_info(coordinator)
        area = build_area_device_info(coordinator, 5)
        door = build_door_device_info(coordinator, 6)
        xbus = build_xbus_device_info(coordinator, 7)

    assert panel["name"] == "SPC"
    assert panel["model"] == "SPC"
    assert area["name"] == "Area 5"
    assert door["name"] == "Zone porte"
    assert xbus["name"] == "X-BUS 7"
    assert "via_device_id" not in area
