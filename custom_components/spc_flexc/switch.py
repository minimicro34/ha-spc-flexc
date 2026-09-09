"""Switch entities for SPC FlexC controls."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .flexc.device import build_area_device_info, build_panel_device_info
from .mapping_gate_coordinator import SpcFlexCMappingGateCoordinator


class SpcZoneInhibitionSwitch(
    CoordinatorEntity[SpcFlexCMappingGateCoordinator], SwitchEntity
):
    """Represent the inhibition state of one SPC zone."""

    _attr_has_entity_name = True
    _attr_translation_key = "inhibition"

    def __init__(
        self, coordinator: SpcFlexCMappingGateCoordinator, zone_id: int
    ) -> None:
        super().__init__(coordinator)
        self.zone_id = zone_id
        zone = coordinator.data.zones[zone_id]
        zone_name = zone.name or f"Zone {zone_id}"
        self._attr_translation_placeholders = {"zone_name": zone_name}
        self._attr_unique_id = f"{coordinator.entry.entry_id}_zone_{zone_id}_inhibition"
        if zone.area_id is not None and zone.area_id in coordinator.data.areas:
            self._attr_device_info = build_area_device_info(coordinator, zone.area_id)
        else:
            self._attr_device_info = build_panel_device_info(coordinator)

    @property
    def is_on(self) -> bool | None:
        zone = self.coordinator.data.zones.get(self.zone_id)
        return None if zone is None else zone.inhibited

    @property
    def available(self) -> bool:
        zone = self.coordinator.data.zones.get(self.zone_id)
        return zone is not None and zone.inhibited is not None

    @property
    def extra_state_attributes(self) -> dict[str, bool | int | None]:
        zone = self.coordinator.data.zones.get(self.zone_id)
        if zone is None:
            return {}
        return {
            "zone_id": zone.zone_id,
            "inhibit_allowed": zone.inhibit_allowed,
            "deinhibit_allowed": zone.deinhibit_allowed,
        }

    async def async_turn_on(self, **kwargs: object) -> None:
        await self.coordinator.async_inhibit_zone(self.zone_id)

    async def async_turn_off(self, **kwargs: object) -> None:
        await self.coordinator.async_deinhibit_zone(self.zone_id)


class SpcMappingGateSwitch(
    CoordinatorEntity[SpcFlexCMappingGateCoordinator], SwitchEntity
):
    """Represent one configured SPC Mapping Gate output."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: SpcFlexCMappingGateCoordinator, mg_id: int
    ) -> None:
        super().__init__(coordinator)
        self.mg_id = mg_id
        mapping_gate = coordinator.data.mapping_gates[mg_id]
        self._attr_name = mapping_gate.name or f"Output {mg_id}"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_mapping_gate_{mg_id}"
        self._attr_device_info = build_panel_device_info(coordinator)

    @property
    def is_on(self) -> bool | None:
        mapping_gate = self.coordinator.data.mapping_gates.get(self.mg_id)
        return None if mapping_gate is None else mapping_gate.state

    @property
    def available(self) -> bool:
        mapping_gate = self.coordinator.data.mapping_gates.get(self.mg_id)
        return mapping_gate is not None and mapping_gate.state is not None

    @property
    def extra_state_attributes(self) -> dict[str, int | str | None]:
        mapping_gate = self.coordinator.data.mapping_gates.get(self.mg_id)
        if mapping_gate is None:
            return {}
        return {
            "mg_id": mapping_gate.mg_id,
            "mg_name": mapping_gate.name,
        }

    async def async_turn_on(self, **kwargs: object) -> None:
        await self.coordinator.async_set_mapping_gate(self.mg_id, True)

    async def async_turn_off(self, **kwargs: object) -> None:
        await self.coordinator.async_set_mapping_gate(self.mg_id, False)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up SPC FlexC switches."""
    coordinator: SpcFlexCMappingGateCoordinator = entry.runtime_data
    known_zones: set[int] = set()
    known_mapping_gates: set[int] = set()

    def add_switches() -> None:
        entities: list[SwitchEntity] = []
        for zone_id, zone in coordinator.data.zones.items():
            if zone_id in known_zones:
                continue
            if zone.inhibit_allowed is not True and zone.inhibited is not True:
                continue
            known_zones.add(zone_id)
            entities.append(SpcZoneInhibitionSwitch(coordinator, zone_id))

        for mg_id in coordinator.data.mapping_gates:
            if mg_id in known_mapping_gates:
                continue
            known_mapping_gates.add(mg_id)
            entities.append(SpcMappingGateSwitch(coordinator, mg_id))

        if entities:
            async_add_entities(entities)

    add_switches()
    entry.async_on_unload(coordinator.async_add_listener(add_switches))
