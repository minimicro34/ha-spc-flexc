"""Sensor entities for the SPC FlexC integration."""

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfFrequency,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SpcFlexCCoordinator
from .flexc.device import (
    build_door_device_info,
    build_xbus_device_info,
    migrate_xbus_registry_identity,
)
from .models import AtpState, DoorState

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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: SpcFlexCCoordinator = entry.runtime_data
    async_add_entities(
        [SpcPanelSensor(coordinator, description) for description in DESCRIPTIONS]
        + [SpcLastEventDiagnosticSensor(coordinator)]
    )
    known_ats: set[int] = set()
    known_atps: set[tuple[int, int]] = set()
    known_doors: set[int] = set()
    known_xbus: set[str] = set()

    def add_dynamic_entities() -> None:
        entities: list[SensorEntity] = []
        for ats_id, ats in coordinator.data.ats.items():
            if ats_id not in known_ats:
                known_ats.add(ats_id)
                entities.append(SpcAtsActivePathSensor(coordinator, ats_id))
            for atp_id in ats.atps:
                key = (ats_id, atp_id)
                if key in known_atps:
                    continue
                known_atps.add(key)
                entities.append(SpcAtpLastTxSensor(coordinator, ats_id, atp_id))

        for door_id in coordinator.data.doors:
            if door_id in known_doors:
                continue
            known_doors.add(door_id)
            entities.extend(
                (
                    SpcDoorStatusSensor(coordinator, door_id),
                    SpcDoorModeSensor(coordinator, door_id),
                )
            )

        for device_id, device in coordinator.data.xbus_devices.items():
            if device_id in known_xbus:
                continue
            known_xbus.add(device_id)
            for suffix in ("aux_voltage", "aux_current", "diagnostics", "device_id"):
                migrate_xbus_registry_identity(coordinator, device_id, "sensor", suffix)
            if device.device_type in (2, 6):
                for suffix in ("input_count", "output_count"):
                    migrate_xbus_registry_identity(
                        coordinator, device_id, "sensor", suffix
                    )
            entities.extend(
                (
                    SpcXBusAuxVoltageSensor(coordinator, device_id),
                    SpcXBusAuxCurrentSensor(coordinator, device_id),
                    SpcXBusDiagnosticSensor(coordinator, device_id),
                    SpcXBusInventorySensor(
                        coordinator, device_id, "device_id", diagnostic=True
                    ),
                )
            )
            if device.device_type in (2, 6):
                entities.extend(
                    (
                        SpcXBusInventorySensor(coordinator, device_id, "input_count"),
                        SpcXBusInventorySensor(coordinator, device_id, "output_count"),
                    )
                )

        if entities:
            async_add_entities(entities)

    add_dynamic_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_dynamic_entities))


# Validated FlexC IDs from SPC event tables and field diagnostics.
# Descriptions are diagnostic metadata, not persistent alarm states.
FLEXC_EVENT_DESCRIPTIONS: dict[int, str] = {
    2100: "Zone input active",
    2101: "Zone input restored",
    2103: "Zone input disconnected",
    2107: "Zone input out of bounds",
    1200: "Zone tamper",
    1300: "Zone tamper restored",
    1800: "Zone trouble",
    1900: "Zone trouble restored",
    4002: "User panic",
    4009: "User medical alarm",
    4011: "User hold-up",
    3523: "Confirmed hold-up",
    8026: "Wireless keypad medical alarm",
    8027: "Wireless keypad medical restore",
    8028: "Wireless keypad fire alarm",
    8029: "Wireless keypad fire restore",
    8030: "Wireless keypad panic alarm",
    8031: "Wireless keypad panic restore",
    5348: "X-BUS keypad panic alarm",
    5349: "X-BUS keypad panic restore",
    5350: "X-BUS keypad fire alarm",
    5351: "X-BUS keypad fire restore",
    5352: "X-BUS keypad medical alarm",
    5353: "X-BUS keypad medical restore",
    8006: "Wireless device tamper",
    8007: "Wireless device tamper restore",
    8012: "Wireless device low battery",
    8013: "Wireless device battery restore",
    8014: "Wireless device fault",
    8015: "Wireless device fault restore",
    6002: "FlexC path down",
    6003: "FlexC path restored",
    6004: "ATS down",
    6005: "ATS restored",
    7011: "Configuration changed",
}


# Zone event suffixes identify the SPC zone type. Names below are
# documented mappings; other suffixes retain their numeric type rather
# than guessing a misleading human-readable label.
FLEXC_ZONE_EVENT_TYPES: dict[int, str] = {
    0: "Alarm Zone",
    1: "Entry / Exit",
    3: "Fire",
    8: "Tamper",
    12: "Unused Zone",
    15: "Detector Fault",
    23: "Glass Break",
}

for _base, _prefix, _restored in (
    (1200, "Zone tamper", False),
    (1300, "Zone tamper", True),
    (1800, "Zone trouble", False),
    (1900, "Zone trouble", True),
):
    for _suffix in range(24):
        _zone_type = FLEXC_ZONE_EVENT_TYPES.get(_suffix, f"Zone type {_suffix}")
        FLEXC_EVENT_DESCRIPTIONS[_base + _suffix] = (
            f"{_prefix} restored [{_zone_type}]"
            if _restored
            else f"{_prefix} [{_zone_type}]"
        )


# Origin is intentionally separate from alarm state: user-triggered panic
# events may not provide AREA_ID or a matching restore event.
def _flexc_event_origin(event_id: int) -> str | None:
    if event_id in (4002, 4009, 4011, 3523):
        return "user"
    if event_id in (8026, 8027, 8028, 8029, 8030, 8031):
        return "wireless_keypad"
    if event_id in (5348, 5349, 5350, 5351, 5352, 5353):
        return "xbus_keypad"
    if event_id in (8006, 8007, 8012, 8013, 8014, 8015):
        return "wireless_device"
    if event_id in (6002, 6003, 6004, 6005):
        return "communication"
    if event_id == 7011:
        return "configuration"
    return None


# Transient events are diagnostic observations, not latched alarm states.
FLEXC_ALARM_EVENTS: dict[int, tuple[str, str]] = {
    4002: ("panic", "trigger"),
    4009: ("medical", "trigger"),
    4011: ("hold_up", "trigger"),
    3523: ("hold_up", "confirmed"),
    8026: ("medical", "trigger"),
    8027: ("medical", "restore"),
    8028: ("fire", "trigger"),
    8029: ("fire", "restore"),
    8030: ("panic", "trigger"),
    8031: ("panic", "restore"),
    5348: ("panic", "trigger"),
    5349: ("panic", "restore"),
    5350: ("fire", "trigger"),
    5351: ("fire", "restore"),
    5352: ("medical", "trigger"),
    5353: ("medical", "restore"),
}


class SpcLastEventDiagnosticSensor(
    CoordinatorEntity[SpcFlexCCoordinator], SensorEntity
):
    """Expose bounded FlexC event identifiers without verbose INFO logging."""

    _attr_has_entity_name = True
    _attr_name = "Last FlexC event ID"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: SpcFlexCCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id(coordinator)}_last_flexc_event_id"
        self._attr_device_info = build_device_info(coordinator)

    @property
    def native_value(self) -> int | None:
        last = getattr(self.coordinator, "_last_event_identifiers", None)
        return last["event_id"] if last is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        last = getattr(self.coordinator, "_last_event_identifiers", None)
        if last is None:
            return {"recent_events": []}
        alarm = FLEXC_ALARM_EVENTS.get(last["event_id"])
        return {
            "area_id": last["area_id"],
            "zone_id": last["zone_id"],
            "event_description": FLEXC_EVENT_DESCRIPTIONS.get(last["event_id"]),
            "event_origin": _flexc_event_origin(last["event_id"]),
            "alarm_type": alarm[0] if alarm else None,
            "alarm_transition": alarm[1] if alarm else None,
            "recent_events": [
                {
                    **event,
                    "description": FLEXC_EVENT_DESCRIPTIONS.get(event["event_id"]),
                    "origin": _flexc_event_origin(event["event_id"]),
                    "alarm_type": FLEXC_ALARM_EVENTS.get(
                        event["event_id"], (None, None)
                    )[0],
                    "alarm_transition": FLEXC_ALARM_EVENTS.get(
                        event["event_id"], (None, None)
                    )[1],
                }
                for event in getattr(self.coordinator, "_recent_event_identifiers", [])
            ],
        }


class SpcPanelSensor(CoordinatorEntity[SpcFlexCCoordinator], SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: SpcFlexCCoordinator, description: SensorEntityDescription
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id(coordinator)}_{description.key}"
        self._attr_device_info = build_device_info(coordinator)

    @property
    def native_value(self) -> float | None:
        return getattr(self.coordinator.data.panel, self.entity_description.key)


def build_device_info(coordinator: SpcFlexCCoordinator) -> DeviceInfo:
    panel = coordinator.data.panel
    serial = panel.serial_number or coordinator.entry.entry_id
    name = panel.installation_name or "SPC"
    model = f"SPC{panel.spc_variant}" if panel.spc_variant else panel.spc_type or "SPC"
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


def entry_id(coordinator: SpcFlexCCoordinator) -> str:
    return coordinator.entry.entry_id


class SpcAtsActivePathSensor(CoordinatorEntity[SpcFlexCCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SpcFlexCCoordinator, ats_id: int) -> None:
        super().__init__(coordinator)
        self.ats_id = ats_id
        ats = coordinator.data.ats[ats_id]
        self._attr_name = f"{ats.name or f'ATS {ats_id}'} active path"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_ats_{ats_id}_active_path"
        self._attr_device_info = build_device_info(coordinator)

    @property
    def available(self) -> bool:
        return self.ats_id in self.coordinator.data.ats

    @property
    def native_value(self) -> str | None:
        ats = self.coordinator.data.ats.get(self.ats_id)
        if ats is None:
            return None
        for atp in ats.atps.values():
            if atp.active is True:
                return atp.name or f"ATP {atp.atp_id}"
        return None


class SpcAtpLastTxSensor(CoordinatorEntity[SpcFlexCCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self, coordinator: SpcFlexCCoordinator, ats_id: int, atp_id: int
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

    def _atp(self) -> AtpState | None:
        ats = self.coordinator.data.ats.get(self.ats_id)
        return None if ats is None else ats.atps.get(self.atp_id)

    @property
    def available(self) -> bool:
        return self._atp() is not None

    @property
    def native_value(self) -> datetime | None:
        atp = self._atp()
        return None if atp is None else atp.last_tx_ok_timestamp


class SpcDoorSensorBase(CoordinatorEntity[SpcFlexCCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: SpcFlexCCoordinator, door_id: int) -> None:
        super().__init__(coordinator)
        self.door_id = door_id
        self._attr_device_info = build_door_device_info(coordinator, door_id)

    def _door(self) -> DoorState | None:
        return self.coordinator.data.doors.get(self.door_id)

    @property
    def available(self) -> bool:
        return self._door() is not None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        door = self._door()
        if door is None:
            return {}
        return {
            "door_id": door.door_id,
            "zone_id": door.zone_id,
            "zone_name": door.zone_name,
            "area_id": door.area_id,
            "area_name": door.area_name,
            "area_side_1": door.area_side_1,
            "area_side_1_name": door.area_side_1_name,
            "dps_input": door.dps_input,
            "drs_input": door.drs_input,
            "reader1_format": door.reader1_format,
            "reader2_format": door.reader2_format,
            "entry_exit": door.entry_exit,
            "normal_allowed": door.normal_allowed,
            "lock_allowed": door.lock_allowed,
            "raw_status": door.status,
            "raw_mode": door.mode,
        }


class SpcDoorStatusSensor(SpcDoorSensorBase):
    def __init__(self, coordinator: SpcFlexCCoordinator, door_id: int) -> None:
        super().__init__(coordinator, door_id)
        self._attr_name = "Status"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_door_{door_id}_status"

    @property
    def native_value(self) -> int | None:
        door = self._door()
        return None if door is None else door.status


class SpcDoorModeSensor(SpcDoorSensorBase):
    def __init__(self, coordinator: SpcFlexCCoordinator, door_id: int) -> None:
        super().__init__(coordinator, door_id)
        self._attr_name = "Mode"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_door_{door_id}_mode"

    @property
    def native_value(self) -> int | None:
        door = self._door()
        return None if door is None else door.mode


class SpcXBusSensorBase(CoordinatorEntity[SpcFlexCCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: SpcFlexCCoordinator, serial_number: str) -> None:
        super().__init__(coordinator)
        self.serial_number = serial_number
        self._attr_device_info = build_xbus_device_info(coordinator, serial_number)

    @property
    def available(self) -> bool:
        return self.serial_number in self.coordinator.data.xbus_devices


class SpcXBusAuxVoltageSensor(SpcXBusSensorBase):
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_suggested_display_precision = 1
    _attr_translation_key = "xbus_aux_voltage"

    def __init__(self, coordinator: SpcFlexCCoordinator, serial_number: str) -> None:
        super().__init__(coordinator, serial_number)
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_xbus_{serial_number}_aux_voltage"
        )

    @property
    def native_value(self) -> float | None:
        device = self.coordinator.data.xbus_devices.get(self.serial_number)
        return None if device is None else device.aux_voltage


class SpcXBusAuxCurrentSensor(SpcXBusSensorBase):
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.MILLIAMPERE
    _attr_translation_key = "xbus_aux_current"

    def __init__(self, coordinator: SpcFlexCCoordinator, serial_number: str) -> None:
        super().__init__(coordinator, serial_number)
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_xbus_{serial_number}_aux_current"
        )

    @property
    def native_value(self) -> float | None:
        device = self.coordinator.data.xbus_devices.get(self.serial_number)
        return None if device is None else device.aux_current


class SpcXBusDiagnosticSensor(SpcXBusSensorBase):
    _attr_translation_key = "xbus_diagnostics"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SpcFlexCCoordinator, serial_number: str) -> None:
        super().__init__(coordinator, serial_number)
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_xbus_{serial_number}_diagnostics"
        )

    @property
    def native_value(self) -> str | None:
        device = self.coordinator.data.xbus_devices.get(self.serial_number)
        return None if device is None else device.status_raw

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        device = self.coordinator.data.xbus_devices.get(self.serial_number)
        if device is None:
            return {}
        return {
            "xbus_device_id": device.device_id,
            "name": device.name,
            "serial_number": device.serial_number,
            "device_type": device.device_type,
            "hardware_id": device.hardware_id,
            "input_count": device.input_count,
            "output_count": device.output_count,
            "version": device.version,
            "rf_type": device.rf_type,
            "rf_version": device.rf_version,
            "reader_type": device.reader_type,
            "position_1": device.position_1,
            "position_2": device.position_2,
            "psu_type": device.psu_type,
            "sia_address": device.sia_address,
            "status_raw": device.status_raw,
            "input_raw": device.input_raw,
            "alert_raw": device.alert_raw,
            "inhibit_raw": device.inhibit_raw,
            "isolate_raw": device.isolate_raw,
        }


class SpcXBusInventorySensor(SpcXBusSensorBase):
    """Expose a small validated X-BUS inventory field."""

    def __init__(
        self,
        coordinator: SpcFlexCCoordinator,
        serial_number: str,
        field: str,
        *,
        diagnostic: bool = False,
    ) -> None:
        super().__init__(coordinator, serial_number)
        self.field = field
        self._attr_translation_key = f"xbus_{field}"
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_xbus_{serial_number}_{field}"
        )
        if diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> int | None:
        device = self.coordinator.data.xbus_devices.get(self.serial_number)
        return None if device is None else getattr(device, self.field)
