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
        section = getattr(
            self.coordinator.data,
            self.section,
        )

        return getattr(
            section,
            self.entity_description.key,
        )


def build_device_info(coordinator) -> DeviceInfo:
    """Return the SPC panel device information."""
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
