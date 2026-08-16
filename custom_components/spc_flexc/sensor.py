from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import (
    CONF_HOST,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfFrequency,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

DESCRIPTIONS = (
    SensorEntityDescription(
        key="battery_voltage",
        name="Battery voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    SensorEntityDescription(
        key="aux_voltage",
        name="Aux voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    SensorEntityDescription(
        key="aux_current",
        name="Aux current",
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
    ),
    SensorEntityDescription(
        key="ac_frequency",
        name="AC frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities([SpcPanelSensor(coordinator, d) for d in DESCRIPTIONS])


class SpcPanelSensor(CoordinatorEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(self, coordinator, description):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id(coordinator)}_{description.key}"
        self._attr_device_info = build_device_info(coordinator)

    @property
    def native_value(self):
        """Return the sensor value."""
        return self.coordinator.data.panel.get(self.entity_description.key)


def build_device_info(coordinator) -> DeviceInfo:
    """Return the SPC panel device information."""
    panel = coordinator.data.panel

    serial = (
        panel.get("serial_number")
        or panel.get("SPC_SERIAL_NO")
        or coordinator.entry.entry_id
    )

    name = panel.get("installation_name") or panel.get("INSTALLATION_NAME") or "SPC"

    model = panel.get("spc_type") or panel.get("SPC_TYPE") or "SPC"

    return DeviceInfo(
        identifiers={(DOMAIN, str(serial))},
        name=str(name),
        manufacturer="Vanderbilt",
        model=str(model),
        serial_number=str(serial),
        sw_version=panel.get("spc_fw_version") or panel.get("SPC_FW_VERSION"),
        hw_version=panel.get("spc_hw_version") or panel.get("SPC_HW_VERSION"),
        configuration_url=f"http://{coordinator.entry.data[CONF_HOST]}",
    )


def entry_id(c):
    return c.entry.entry_id
