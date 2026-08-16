from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import CONF_HOST, EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

PANEL = (
    BinarySensorEntityDescription(key="internal_bells", name="Internal bells"),
    BinarySensorEntityDescription(key="external_bells", name="External bells"),
    BinarySensorEntityDescription(key="engineer_mode", name="Engineer mode"),
)

FAULTS = (
    BinarySensorEntityDescription(key="modem_1_fault", name="Modem 1 fault"),
    BinarySensorEntityDescription(
        key="modem_1_line_fault",
        name="Modem 1 line fault",
    ),
    BinarySensorEntityDescription(key="rf_jamming", name="RF jamming"),
    BinarySensorEntityDescription(
        key="xbus_mains_fault",
        name="X-BUS mains fault",
    ),
    BinarySensorEntityDescription(
        key="xbus_battery_fault",
        name="X-BUS battery fault",
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    c = entry.runtime_data

    async_add_entities(
        [SpcBinary(c, d, "panel") for d in PANEL]
        + [SpcBinary(c, d, "faults") for d in FAULTS]
    )


class SpcBinary(CoordinatorEntity, BinarySensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(self, coordinator, description, section):
        super().__init__(coordinator)

        self.entity_description = description
        self.section = section

        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"

        self._attr_device_info = build_device_info(coordinator)

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor state."""
        value = self.coordinator.data.get(self.entity_description.key)

        if value is None:
            return None

        return bool(value)


def build_device_info(coordinator) -> DeviceInfo:
    """Return the SPC panel device information."""
    data = coordinator.data

    panel = getattr(data, "panel", None)

    if isinstance(panel, dict):
        device_data = panel
    elif isinstance(data, dict):
        device_data = data
    else:
        device_data = {}

    serial = (
        device_data.get("serial_number")
        or device_data.get("SPC_SERIAL_NO")
        or coordinator.entry.entry_id
    )

    name = (
        device_data.get("installation_name")
        or device_data.get("INSTALLATION_NAME")
        or "SPC"
    )

    model = device_data.get("spc_type") or device_data.get("SPC_TYPE") or "SPC"

    return DeviceInfo(
        identifiers={(DOMAIN, str(serial))},
        name=str(name),
        manufacturer="Vanderbilt",
        model=str(model),
        serial_number=str(serial),
        sw_version=device_data.get("spc_fw_version")
        or device_data.get("SPC_FW_VERSION"),
        hw_version=device_data.get("spc_hw_version")
        or device_data.get("SPC_HW_VERSION"),
        configuration_url=f"http://{coordinator.entry.data[CONF_HOST]}",
    )
