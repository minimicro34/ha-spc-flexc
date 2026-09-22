"""Tests for SPC FlexC Home Assistant device helpers."""

from unittest.mock import MagicMock, patch

from custom_components.spc_flexc.flexc.device import (
    _xbus_model,
    build_area_device_info,
    build_door_device_info,
    build_panel_device_info,
    build_xbus_device_info,
    migrate_xbus_registry_identity,
)
from custom_components.spc_flexc.models import (
    AreaState,
    DoorState,
    SpcState,
    XBusDeviceState,
)


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
    coordinator.data.xbus_devices["XB3"] = XBusDeviceState(
        device_id=3,
        name="Extension",
        device_type=2,
        input_count=8,
        output_count=2,
        serial_number="XB3",
        version="1.2",
    )

    with patch(
        "custom_components.spc_flexc.flexc.device.dr.async_get_device_id_by_identifier",
        return_value="parent-id",
        create=True,
    ):
        panel = build_panel_device_info(coordinator)
        area = build_area_device_info(coordinator, 1)
        door = build_door_device_info(coordinator, 2)
        xbus = build_xbus_device_info(coordinator, "XB3")

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
    coordinator.data.xbus_devices["XB7"] = XBusDeviceState(
        device_id=7, serial_number="XB7"
    )

    with patch(
        "custom_components.spc_flexc.flexc.device.dr.async_get_device_id_by_identifier",
        None,
        create=True,
    ):
        panel = build_panel_device_info(coordinator)
        area = build_area_device_info(coordinator, 5)
        door = build_door_device_info(coordinator, 6)
        xbus = build_xbus_device_info(coordinator, "XB7")

    assert panel["name"] == "SPC"
    assert panel["model"] == "SPC"
    assert area["name"] == "Area 5"
    assert door["name"] == "Zone porte"
    assert xbus["name"] == "X-BUS 7"
    assert "via_device_id" not in area


def test_migrate_unambiguous_xbus_registry_identity() -> None:
    coordinator = _coordinator()
    coordinator.data.xbus_devices["XB7"] = XBusDeviceState(
        device_id=7, serial_number="XB7"
    )
    entity_registry = MagicMock()
    entity_registry.async_get_entity_id.return_value = "sensor.legacy_xbus"
    device_registry = MagicMock()
    old_device = MagicMock()
    old_device.id = "legacy-device"
    device_registry.async_get_device.return_value = old_device

    with (
        patch(
            "custom_components.spc_flexc.flexc.device.er.async_get",
            return_value=entity_registry,
        ),
        patch(
            "custom_components.spc_flexc.flexc.device.dr.async_get",
            return_value=device_registry,
        ),
    ):
        migrate_xbus_registry_identity(coordinator, "XB7", "sensor", "aux_voltage")

    entity_registry.async_update_entity.assert_called_once_with(
        "sensor.legacy_xbus",
        new_unique_id="entry_xbus_XB7_aux_voltage",
    )
    entity_registry.async_remove.assert_not_called()
    device_registry.async_update_device.assert_called_once_with(
        "legacy-device",
        new_identifiers={("spc_flexc", "SERIAL_xbus_XB7")},
    )
    device_registry.async_remove_device.assert_not_called()


def test_remove_ambiguous_legacy_xbus_entity_identity_without_device_removal() -> None:
    coordinator = _coordinator()
    coordinator.data.xbus_devices["AAA"] = XBusDeviceState(
        device_id=1, serial_number="AAA"
    )
    coordinator.data.xbus_devices["BBB"] = XBusDeviceState(
        device_id=1, serial_number="BBB"
    )
    entity_registry = MagicMock()
    entity_registry.async_get_entity_id.return_value = "sensor.legacy_xbus"
    device_registry = MagicMock()
    old_device = MagicMock()
    old_device.id = "legacy-device"
    device_registry.async_get_device.return_value = old_device

    with (
        patch(
            "custom_components.spc_flexc.flexc.device.er.async_get",
            return_value=entity_registry,
        ),
        patch(
            "custom_components.spc_flexc.flexc.device.dr.async_get",
            return_value=device_registry,
        ),
    ):
        migrate_xbus_registry_identity(coordinator, "AAA", "sensor", "aux_voltage")

    entity_registry.async_update_entity.assert_not_called()
    entity_registry.async_remove.assert_called_once_with("sensor.legacy_xbus")
    device_registry.async_update_device.assert_not_called()
    device_registry.async_remove_device.assert_not_called()


def test_ambiguous_xbus_devices_keep_distinct_serial_device_info() -> None:
    coordinator = _coordinator()
    coordinator.data.xbus_devices["EXPANDER"] = XBusDeviceState(
        device_id=1,
        name="SPCE650 ID 1",
        device_type=2,
        serial_number="EXPANDER",
    )
    coordinator.data.xbus_devices["KEYPAD"] = XBusDeviceState(
        device_id=1,
        name="Maison",
        device_type=7,
        serial_number="KEYPAD",
    )
    coordinator.data.xbus_devices["DOOR"] = XBusDeviceState(
        device_id=1,
        name="SPCA210 ID 1",
        device_type=6,
        serial_number="DOOR",
    )

    with patch(
        "custom_components.spc_flexc.flexc.device.dr.async_get_device_id_by_identifier",
        return_value="panel-device",
        create=True,
    ):
        expander = build_xbus_device_info(coordinator, "EXPANDER")
        keypad = build_xbus_device_info(coordinator, "KEYPAD")
        door = build_xbus_device_info(coordinator, "DOOR")

    assert expander["identifiers"] == {("spc_flexc", "SERIAL_xbus_EXPANDER")}
    assert keypad["identifiers"] == {("spc_flexc", "SERIAL_xbus_KEYPAD")}
    assert door["identifiers"] == {("spc_flexc", "SERIAL_xbus_DOOR")}
    assert len(
        {
            next(iter(expander["identifiers"])),
            next(iter(keypad["identifiers"])),
            next(iter(door["identifiers"])),
        }
    ) == 3
