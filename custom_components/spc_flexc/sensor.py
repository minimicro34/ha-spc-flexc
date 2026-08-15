from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import UnitOfElectricPotential, UnitOfElectricCurrent, UnitOfFrequency
from homeassistant.helpers.update_coordinator import CoordinatorEntity

DESCRIPTIONS = (
    SensorEntityDescription(key="battery_voltage", name="Battery voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT),
    SensorEntityDescription(key="aux_voltage", name="Aux voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT),
    SensorEntityDescription(key="aux_current", name="Aux current",
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE),
    SensorEntityDescription(key="ac_frequency", name="AC frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ),
)

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities([SpcPanelSensor(coordinator, d) for d in DESCRIPTIONS])

class SpcPanelSensor(CoordinatorEntity, SensorEntity):
    _attr_entity_category = "diagnostic"
    def __init__(self, coordinator, description):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id(coordinator)}_{description.key}"
    @property
    def native_value(self):
        return getattr(self.coordinator.data.panel, self.entity_description.key)

def entry_id(c):
    return c.entry.entry_id
