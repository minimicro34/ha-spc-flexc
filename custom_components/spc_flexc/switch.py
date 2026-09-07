"""Switch entities for SPC FlexC zone inhibition control."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .flexc.device import build_area_device_info, build_panel_device_info
from .zone_control_coordinator import SpcFlexCZoneControlCoordinator


class SpcZoneInhibitionSwitch(
    CoordinatorEntity[SpcFlexCZoneControlCoordinator],
    SwitchEntity,
):
    """Represent the inhibition state of one SPC zone."""

    _attr_has_entity_name = True
    _attr_name = "Inhibition"

    def __init__(
        self,
        coordinator: SpcFlexCZoneControlCoordinator,
        zone_id: int,
    ) -> None:
        super().__init__(coordinator)
        self.zone_id = zone_id

        zone = coordinator.data.zones[zone_id]
        self._attr_unique_id = f"{coordinator.entry.entry_id}_zone_{zone_id}_inhibition"

        if zone.area_id is not None and zone.area_id in coordinator.data.areas:
            self._attr_device_info = build_area_device_info(coordinator, zone.area_id)
        else:
            self._attr_device_info = build_panel_device_info(coordinator)

    @property
    def is_on(self) -> bool | None:
        """Return whether the zone is currently inhibited."""
        zone = self.coordinator.data.zones.get(self.zone_id)
        if zone is None:
            return None
        return zone.inhibited

    @property
    def available(self) -> bool:
        """Return whether the zone and its inhibition state are known."""
        zone = self.coordinator.data.zones.get(self.zone_id)
        return zone is not None and zone.inhibited is not None

    @property
    def extra_state_attributes(self) -> dict[str, bool | int | None]:
        """Return current FlexC inhibition capabilities."""
        zone = self.coordinator.data.zones.get(self.zone_id)
        if zone is None:
            return {}
        return {
            "zone_id": zone.zone_id,
            "inhibit_allowed": zone.inhibit_allowed,
            "deinhibit_allowed": zone.deinhibit_allowed,
        }

    async def async_turn_on(self, **kwargs: object) -> None:
        """Inhibit the SPC zone."""
        await self.coordinator.async_inhibit_zone(self.zone_id)

    async def async_turn_off(self, **kwargs: object) -> None:
        """De-inhibit the SPC zone."""
        await self.coordinator.async_deinhibit_zone(self.zone_id)


async def async_setup_entry(
    hass,
    entry,
    async_add_entities,
) -> None:
    """Set up SPC FlexC zone inhibition switches."""
    coordinator: SpcFlexCZoneControlCoordinator = entry.runtime_data
    known_zones: set[int] = set()

    def add_zone_switches() -> None:
        """Create inhibition switches for newly discovered zones."""
        entities: list[SwitchEntity] = []

        for zone_id, zone in coordinator.data.zones.items():
            if zone_id in known_zones:
                continue

            if zone.inhibit_allowed is not True and zone.inhibited is not True:
                continue

            known_zones.add(zone_id)
            entities.append(SpcZoneInhibitionSwitch(coordinator, zone_id))

        if entities:
            async_add_entities(entities)

    add_zone_switches()

    def coordinator_updated() -> None:
        """Handle newly discovered coordinator zones."""
        add_zone_switches()

    entry.async_on_unload(coordinator.async_add_listener(coordinator_updated))
