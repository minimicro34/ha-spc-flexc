"""Home Assistant device helpers for SPC FlexC."""

from typing import Any, cast

from homeassistant.const import CONF_HOST
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from ..const import DOMAIN
from ..coordinator import SpcFlexCCoordinator


def build_panel_device_info(
    coordinator: SpcFlexCCoordinator,
) -> DeviceInfo:
    """Return the main SPC panel device information."""
    panel = coordinator.data.panel

    serial = panel.serial_number or coordinator.entry.entry_id
    name = panel.installation_name or "SPC"

    if panel.spc_variant:
        model = f"SPC{panel.spc_variant}"
    else:
        model = panel.spc_type or "SPC"

    return DeviceInfo(
        identifiers={(DOMAIN, str(serial))},
        name=name,
        manufacturer="Vanderbilt",
        model=model,
        serial_number=str(serial),
        sw_version=panel.firmware_version,
        hw_version=panel.hardware_version,
        configuration_url=f"http://{coordinator.entry.data[CONF_HOST]}",
    )


def build_area_device_info(
    coordinator: SpcFlexCCoordinator,
    area_id: int,
) -> DeviceInfo:
    """Return the Home Assistant device for one SPC area."""
    panel = coordinator.data.panel
    area = coordinator.data.areas[area_id]

    serial = panel.serial_number or coordinator.entry.entry_id

    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{serial}_area_{area_id}")},
        name=area.name or f"Area {area_id}",
        manufacturer="Vanderbilt",
        model="SPC Area",
    )

    _set_parent_device(coordinator, device_info, (DOMAIN, str(serial)))
    return device_info


def build_door_device_info(
    coordinator: SpcFlexCCoordinator,
    door_id: int,
) -> DeviceInfo:
    """Return the Home Assistant device for one SPC access-control door."""
    panel = coordinator.data.panel
    door = coordinator.data.doors[door_id]
    serial = panel.serial_number or coordinator.entry.entry_id

    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{serial}_door_{door_id}")},
        name=door.name or door.zone_name or f"Door {door_id}",
        manufacturer="Vanderbilt",
        model="SPC Door",
    )

    parent_identifier = (DOMAIN, str(serial))
    if door.area_id is not None and door.area_id in coordinator.data.areas:
        parent_identifier = (DOMAIN, f"{serial}_area_{door.area_id}")

    _set_parent_device(coordinator, device_info, parent_identifier)
    return device_info


def _xbus_model(device_type: int | None, input_count: int | None, output_count: int | None) -> str:
    """Return only empirically validated X-BUS family/model labels."""
    if device_type == 1:
        return "SPC Keypad"
    if device_type == 7:
        return "SPC Comfort Keypad"
    if device_type == 6 and input_count == 4 and output_count == 2:
        return "SPCA210 2-door expander"
    if device_type == 2:
        if input_count == 8 and output_count == 2:
            return "SPCE650 I/O expander (8 inputs / 2 outputs)"
        if input_count == 0 and output_count == 8:
            return "SPCE450 output expander (8 outputs)"
        return "SPC I/O expander"
    return "SPC X-BUS"


def build_xbus_device_info(
    coordinator: SpcFlexCCoordinator,
    device_id: int,
) -> DeviceInfo:
    """Return a dedicated Home Assistant device for one X-BUS peripheral."""
    panel = coordinator.data.panel
    device = coordinator.data.xbus_devices[device_id]
    panel_serial = panel.serial_number or coordinator.entry.entry_id

    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{panel_serial}_xbus_{device_id}")},
        name=device.name or f"X-BUS {device_id}",
        manufacturer="Vanderbilt",
        model=_xbus_model(device.device_type, device.input_count, device.output_count),
        serial_number=device.serial_number,
        sw_version=device.version,
    )

    _set_parent_device(coordinator, device_info, (DOMAIN, str(panel_serial)))
    return device_info


def _set_parent_device(
    coordinator: SpcFlexCCoordinator,
    device_info: DeviceInfo,
    parent_identifier: tuple[str, str],
) -> None:
    """Attach a device using via_device_id when supported by Home Assistant."""
    get_device_id = getattr(dr, "async_get_device_id_by_identifier", None)

    if get_device_id is None:
        return

    parent_device_id = get_device_id(
        coordinator.hass,
        parent_identifier,
        config_entry_id=coordinator.entry.entry_id,
    )

    if parent_device_id is not None:
        cast(dict[str, Any], device_info)["via_device_id"] = parent_device_id
