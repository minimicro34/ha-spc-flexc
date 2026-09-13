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
from .flexc.device import build_door_device_info, build_xbus_device_info
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

XBUS_DIAGNOSTIC_FIELDS = (
    "device_id",
    "device_type",
    "hardware_id",
    "input_count",
    "output_count",
    "rf_type",
    "rf_version",
    "reader_type",
    "position_1",
    "position_2",
    "psu_type",
    "sia_address",
    "status_raw",
    "input_raw",
    "alert_raw",
    "inhibit_raw",
    "isolate_raw",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: SpcFlexCCoordinator = entry.runtime_data
    async_add_entities(
        [SpcPanelSensor(coordinator, description) for description in DESCRIPTIONS]
    )
    known_ats: set[int] = set()
    known_atps: set[tuple[int, int]] = set()
    known_doors: set[int] = set()
    known_xbus: set[int] = set()

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

        for device_id in coordinator.data.xbus_devices:
            if device_id in known_xbus:
                continue
            known_xbus.add(device_id)
            entities.extend(
                (
                    SpcXBusAuxVoltageSensor(coordinator, device_id),
                    SpcXBusAuxCurrentSensor(coordinator, device_id),
                    SpcXBusDiagnosticSensor(coordinator, device_id),
                )
            )
            entities.extend(
                SpcXBusMetadataSensor(coordinator, device_id, field)
                for field in XBUS_DIAGNOSTIC_FIELDS
            )

        if entities:
            async_add_entities(entities)

    add_dynamic_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_dynamic_entities))


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
        """Return the sensor value."""
        return getattr(self.coordinator.data.panel, self.entity_description.key)


def build_device_info(coordinator: SpcFlexCCoordinator) -> DeviceInfo:
    """Return the SPC panel device information."""
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
    """Return the config entry ID."""
    return coordinator.entry.entry_id


class SpcAtsActivePathSensor(CoordinatorEntity[SpcFlexCCoordinator], SensorEntity):
    """Represent the last known active ATP path."""

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


class SpcAtpLastTxSensor(CoordinatorEntity[SpcFlexCCoordinator], SensorEntity):
    """Represent the last successful ATP transmission."""

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
    """Base class for raw SPC door status sensors."""

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
    """Base class for X-BUS diagnostic measurements."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SpcFlexCCoordinator, device_id: int) -> None:
        super().__init__(coordinator)
        self.device_id = device_id
        self._attr_device_info = build_xbus_device_info(coordinator, device_id)

    @property
    def available(self) -> bool:
        return self.device_id in self.coordinator.data.xbus_devices


class SpcXBusAuxVoltageSensor(SpcXBusSensorBase):
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_translation_key = "xbus_aux_voltage"

    def __init__(self, coordinator: SpcFlexCCoordinator, device_id: int) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_xbus_{device_id}_aux_voltage"
        )

    @property
    def native_value(self) -> float | None:
        device = self.coordinator.data.xbus_devices.get(self.device_id)
        return None if device is None else device.aux_voltage


class SpcXBusAuxCurrentSensor(SpcXBusSensorBase):
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.MILLIAMPERE
    _attr_translation_key = "xbus_aux_current"

    def __init__(self, coordinator: SpcFlexCCoordinator, device_id: int) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_xbus_{device_id}_aux_current"
        )

    @property
    def native_value(self) -> float | None:
        device = self.coordinator.data.xbus_devices.get(self.device_id)
        return None if device is None else device.aux_current


class SpcXBusDiagnosticSensor(SpcXBusSensorBase):
    """Expose raw X-BUS metadata without interpreting unvalidated fields."""

    _attr_translation_key = "xbus_diagnostics"

    def __init__(self, coordinator: SpcFlexCCoordinator, device_id: int) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_xbus_{device_id}_diagnostics"
        )

    @property
    def native_value(self) -> str | None:
        device = self.coordinator.data.xbus_devices.get(self.device_id)
        return None if device is None else device.status_raw

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        device = self.coordinator.data.xbus_devices.get(self.device_id)
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


class SpcXBusMetadataSensor(SpcXBusSensorBase):
    """Expose one X-BUS metadata field as a beta diagnostic entity."""

    def __init__(
        self, coordinator: SpcFlexCCoordinator, device_id: int, field: str
    ) -> None:
        super().__init__(coordinator, device_id)
        self.field = field
        self._attr_translation_key = f"xbus_{field}"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_xbus_{device_id}_{field}"

    @property
    def native_value(self) -> str | int | None:
        """Return the raw or inventory X-BUS field without interpretation."""
        device = self.coordinator.data.xbus_devices.get(self.device_id)
        return None if device is None else getattr(device, self.field)
