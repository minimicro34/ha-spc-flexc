from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import CONF_HOST, EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SpcFlexCCoordinator

PANEL = (
    BinarySensorEntityDescription(
        key="internal_bells",
        name="Internal bells",
    ),
    BinarySensorEntityDescription(
        key="external_bells",
        name="External bells",
    ),
    BinarySensorEntityDescription(
        key="engineer_mode",
        name="Engineer mode",
    ),
)

FAULTS = (
    BinarySensorEntityDescription(
        key="modem_1_fault",
        name="Modem 1 fault",
    ),
    BinarySensorEntityDescription(
        key="modem_1_line_fault",
        name="Modem 1 line fault",
    ),
    BinarySensorEntityDescription(
        key="rf_jamming",
        name="RF jamming",
    ),
    BinarySensorEntityDescription(
        key="xbus_mains_fault",
        name="X-BUS mains fault",
    ),
    BinarySensorEntityDescription(
        key="xbus_battery_fault",
        name="X-BUS battery fault",
    ),
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


class SpcBinary(CoordinatorEntity, BinarySensorEntity):
    """Represent a standard SPC binary state."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(self, coordinator, description, section):
        super().__init__(coordinator)

        self.entity_description = description
        self.section = section

        if section == "faults":
            self._attr_device_class = BinarySensorDeviceClass.PROBLEM

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


class SpcAtpFaultSensor(
    CoordinatorEntity[SpcFlexCCoordinator],
    BinarySensorEntity,
):
    """Represent the last known FlexC ATP fault state."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

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

        self._attr_name = f"{atp.name or f'ATP {atp_id}'} fault"
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_ats_{ats_id}_atp_{atp_id}_fault"
        )
        self._attr_device_info = build_device_info(coordinator)

    @property
    def is_on(self) -> bool | None:
        """Return whether the ATP is in fault."""
        ats = self.coordinator.data.ats.get(self.ats_id)

        if ats is None:
            return None

        atp = ats.atps.get(self.atp_id)

        if atp is None:
            return None

        return atp.fault

    @property
    def available(self) -> bool:
        """Return whether a last known ATP state exists."""
        ats = self.coordinator.data.ats.get(self.ats_id)

        if ats is None:
            return False

        return self.atp_id in ats.atps


class SpcFlexCConnectionSensor(
    CoordinatorEntity[SpcFlexCCoordinator],
    BinarySensorEntity,
):
    """FlexC connection availability."""

    _attr_name = "FlexC connection"
    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: SpcFlexCCoordinator,
    ) -> None:
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.entry.entry_id}_flexc_connection"
        self._attr_device_info = build_device_info(coordinator)

    @property
    def is_on(self) -> bool:
        """Return whether the SPC FlexC connection is healthy."""
        return bool(
            self.coordinator.last_update_success and self.coordinator.client.connected
        )


async def async_setup_entry(
    hass,
    entry,
    async_add_entities,
) -> None:
    """Set up SPC FlexC binary sensors."""
    coordinator: SpcFlexCCoordinator = entry.runtime_data

    async_add_entities(
        [SpcBinary(coordinator, description, "panel") for description in PANEL]
        + [SpcBinary(coordinator, description, "faults") for description in FAULTS]
        + [SpcFlexCConnectionSensor(coordinator)]
    )

    known_atps: set[tuple[int, int]] = set()

    def add_atp_entities() -> None:
        """Create binary sensors for newly discovered ATPs."""
        entities: list[BinarySensorEntity] = []

        for ats_id, ats in coordinator.data.ats.items():
            for atp_id in ats.atps:
                key = (ats_id, atp_id)

                if key in known_atps:
                    continue

                known_atps.add(key)

                entities.append(
                    SpcAtpFaultSensor(
                        coordinator,
                        ats_id,
                        atp_id,
                    )
                )

        if entities:
            async_add_entities(entities)

    add_atp_entities()

    entry.async_on_unload(coordinator.async_add_listener(add_atp_entities))
