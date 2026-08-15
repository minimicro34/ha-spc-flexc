from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

PANEL = (
    BinarySensorEntityDescription(key="internal_bells", name="Internal bells"),
    BinarySensorEntityDescription(key="external_bells", name="External bells"),
    BinarySensorEntityDescription(key="engineer_mode", name="Engineer mode"),
)
FAULTS = (
    BinarySensorEntityDescription(key="modem_1_fault", name="Modem 1 fault"),
    BinarySensorEntityDescription(key="modem_1_line_fault", name="Modem 1 line fault"),
    BinarySensorEntityDescription(key="rf_jamming", name="RF jamming"),
    BinarySensorEntityDescription(key="xbus_mains_fault", name="X-BUS mains fault"),
    BinarySensorEntityDescription(key="xbus_battery_fault", name="X-BUS battery fault"),
)

async def async_setup_entry(hass, entry, async_add_entities):
    c = entry.runtime_data
    async_add_entities([SpcBinary(c, d, "panel") for d in PANEL] +
                       [SpcBinary(c, d, "faults") for d in FAULTS])

class SpcBinary(CoordinatorEntity, BinarySensorEntity):
    _attr_entity_category = "diagnostic"
    def __init__(self, coordinator, description, section):
        super().__init__(coordinator)
        self.entity_description = description
        self.section = section
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"
    @property
    def is_on(self):
        return getattr(getattr(self.coordinator.data, self.section), self.entity_description.key)
