from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
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
from .coordinator import SpcFlexCCoordinator

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
    coordinator: SpcFlexCCoordinator = entry.runtime_data

    async_add_entities(
        [SpcPanelSensor(coordinator, description) for description in DESCRIPTIONS]
    )

    known_ats: set[int] = set()
    known_atps: set[tuple[int, int]] = set()

    def add_ats_entities() -> None:
        entities: list[SensorEntity] = []

        for ats_id, ats in coordinator.data.ats.items():
            if ats_id not in known_ats:
                known_ats.add(ats_id)

                entities.append(
                    SpcAtsActivePathSensor(
                        coordinator,
                        ats_id,
                    )
                )

            for atp_id in ats.atps:
                key = (ats_id, atp_id)

                if key in known_atps:
                    continue

                known_atps.add(key)

                entities.append(
                    SpcAtpLastTxSensor(
                        coordinator,
                        ats_id,
                        atp_id,
                    )
                )

        if entities:
            async_add_entities(entities)

    add_ats_entities()

    entry.async_on_unload(coordinator.async_add_listener(add_ats_entities))


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
        return getattr(
            self.coordinator.data.panel,
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


def entry_id(c):
    return c.entry.entry_id


class SpcAtsActivePathSensor(
    CoordinatorEntity[SpcFlexCCoordinator],
    SensorEntity,
):
    """Represent the last known active ATP path."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: SpcFlexCCoordinator,
        ats_id: int,
    ) -> None:
        super().__init__(coordinator)

        self.ats_id = ats_id

        self._attr_name = "Active path"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_ats_{ats_id}_active_path"
        self._attr_device_info = build_device_info(coordinator)

    @property
    def available(self) -> bool:
        """Keep the last known ATS state available."""
        return self.ats_id in self.coordinator.data.ats

    @property
    def native_value(self) -> str | None:
        """Return the last known active ATP path."""
        ats = self.coordinator.data.ats.get(self.ats_id)

        if ats is None:
            return None

        for atp in ats.atps.values():
            if atp.active is True:
                return atp.name or f"ATP {atp.atp_id}"

        return None


class SpcAtpLastTxSensor(
    CoordinatorEntity[SpcFlexCCoordinator],
    SensorEntity,
):
    """Represent the last successful ATP transmission."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: SpcFlexCCoordinator,
        ats_id: int,
        atp_id: int,
    ) -> None:
        super().__init__(coordinator)

        self.ats_id = ats_id
        self.atp_id = atp_id

        atp = coordinator.data.ats[ats_id].atps[atp_id]

        self._attr_name = f"{atp.name or f'ATP {atp_id}'} last TX successful"
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_ats_{ats_id}_atp_{atp_id}_last_tx_ok"
        )
        self._attr_device_info = build_device_info(coordinator)

    def _atp(self):
        """Return the last known ATP state."""
        ats = self.coordinator.data.ats.get(self.ats_id)

        if ats is None:
            return None

        return ats.atps.get(self.atp_id)

    @property
    def available(self) -> bool:
        """Keep the last known timestamp available."""
        return self._atp() is not None

    @property
    def native_value(self):
        """Return the last successful TX timestamp."""
        atp = self._atp()

        if atp is None:
            return None

        return atp.last_tx_ok_timestamp
