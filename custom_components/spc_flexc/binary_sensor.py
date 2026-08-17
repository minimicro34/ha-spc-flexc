from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import CONF_HOST, EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SPC_ZONE_TYPES
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

def zone_device_class(
    zone_type: int | None,
) -> BinarySensorDeviceClass | None:
    """Return the Home Assistant device class for an SPC zone type."""
    if zone_type in (0, 1, 2, 30):
        return BinarySensorDeviceClass.MOTION

    if zone_type == 3:
        return BinarySensorDeviceClass.SMOKE

    if zone_type == 4:
        return BinarySensorDeviceClass.DOOR

    if zone_type == 8:
        return BinarySensorDeviceClass.TAMPER

    if zone_type in (15, 19, 20):
        return BinarySensorDeviceClass.PROBLEM

    if zone_type == 23:
        return BinarySensorDeviceClass.VIBRATION

    if zone_type == 24:
        return BinarySensorDeviceClass.MOISTURE

    if zone_type == 25:
        return BinarySensorDeviceClass.HEAT

    if zone_type in (27, 29):
        return BinarySensorDeviceClass.GAS

    return None

class SpcZoneBinarySensor(
    CoordinatorEntity[SpcFlexCCoordinator],
    BinarySensorEntity,
):
    """Represent the live state of an SPC zone."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SpcFlexCCoordinator,
        zone_id: int,
    ) -> None:
        super().__init__(coordinator)

        self.zone_id = zone_id

        zone = coordinator.data.zones[zone_id]

        self._attr_device_class = zone_device_class(zone.zone_type)
        self._attr_name = zone.name or f"Zone {zone_id}"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_zone_{zone_id}_motion"
        self._attr_device_info = build_device_info(coordinator)

    @property
    def is_on(self) -> bool | None:
        """Return whether the zone is currently active."""
        zone = self.coordinator.data.zones.get(self.zone_id)

        if zone is None:
            return None

        return bool(zone.logic_input)

    @property
    def available(self) -> bool:
        """Return whether the zone is known."""
        return self.zone_id in self.coordinator.data.zones

    @property
    def extra_state_attributes(self) -> dict:
        """Return diagnostic information for the zone."""
        zone = self.coordinator.data.zones.get(self.zone_id)

        if zone is None:
            return {}

        return {
            "zone_id": zone.zone_id,
            "area_id": zone.area_id,
            "spc_zone_type": SPC_ZONE_TYPES.get(zone.zone_type),
            "logic_input": zone.logic_input,
            "status": zone.status,
            "proc_state": zone.proc_state,
            "alarm_state": zone.alarm_state,
            "actuations_since_last_read": zone.actuations_since_last_read,
        }


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
    known_zones: set[int] = set()

    def add_zone_entities() -> None:
        """Create binary sensors for newly discovered zones."""
        entities: list[BinarySensorEntity] = []

        for zone_id in coordinator.data.zones:
            if zone_id in known_zones:
                continue

            known_zones.add(zone_id)

            entities.append(
                SpcZoneBinarySensor(
                    coordinator,
                    zone_id,
                )
            )

        if entities:
            async_add_entities(entities)

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
    add_zone_entities()

    def coordinator_updated() -> None:
        """Handle newly discovered coordinator objects."""
        add_atp_entities()
        add_zone_entities()

    entry.async_on_unload(coordinator.async_add_listener(coordinator_updated))
