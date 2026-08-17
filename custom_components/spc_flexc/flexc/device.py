"""Home Assistant device helpers for SPC FlexC."""

from homeassistant.const import CONF_HOST
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from ..const import DOMAIN
from .coordinator import SpcFlexCCoordinator


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

    panel_device_id = dr.async_get_device_id_by_identifier(
        coordinator.hass,
        (DOMAIN, str(serial)),
        config_entry_id=coordinator.entry.entry_id,
    )

    device_info = DeviceInfo(
        identifiers={
            (
                DOMAIN,
                f"{serial}_area_{area_id}",
            )
        },
        name=area.name or f"Area {area_id}",
        manufacturer="Vanderbilt",
        model="SPC Area",
    )

    if panel_device_id is not None:
        device_info["via_device_id"] = panel_device_id

    return device_info