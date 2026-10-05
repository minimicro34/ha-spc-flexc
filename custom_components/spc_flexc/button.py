"""Button entities for SPC FlexC access-control door actions."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .flexc.device import (
    build_area_device_info,
    build_door_device_info,
    build_panel_device_info,
)
from .zone_control_coordinator import SpcFlexCZoneControlCoordinator


@dataclass(frozen=True, kw_only=True)
class SpcDoorButtonDescription(ButtonEntityDescription):
    """Describe one SPC FlexC door action button."""

    action: int


DOOR_BUTTONS = (
    SpcDoorButtonDescription(
        key="open_momentarily", translation_key="open_momentarily", action=5
    ),
    SpcDoorButtonDescription(
        key="open_permanently", translation_key="open_permanently", action=6
    ),
    SpcDoorButtonDescription(key="set_normal", translation_key="set_normal", action=7),
    SpcDoorButtonDescription(key="lock", translation_key="lock", action=8),
)


class SpcZoneRestoreButton(
    CoordinatorEntity[SpcFlexCZoneControlCoordinator], ButtonEntity
):
    """Restore one SPC zone when the panel explicitly permits it."""

    _attr_has_entity_name = True
    _attr_translation_key = "restore"

    def __init__(
        self, coordinator: SpcFlexCZoneControlCoordinator, zone_id: int
    ) -> None:
        """Initialize a zone restore button."""
        super().__init__(coordinator)
        self.zone_id = zone_id
        zone = coordinator.data.zones[zone_id]
        zone_name = zone.name or f"Zone {zone_id}"
        self._attr_translation_placeholders = {"zone_name": zone_name}
        self._attr_unique_id = f"{coordinator.entry.entry_id}_zone_{zone_id}_restore"
        if zone.area_id is not None and zone.area_id in coordinator.data.areas:
            self._attr_device_info = build_area_device_info(coordinator, zone.area_id)
        else:
            self._attr_device_info = build_panel_device_info(coordinator)

    @property
    def available(self) -> bool:
        """Return whether SPC currently permits restoring this zone."""
        zone = self.coordinator.data.zones.get(self.zone_id)
        return zone is not None and zone.restore_allowed is True

    @property
    def extra_state_attributes(self) -> dict[str, bool | int | None]:
        """Expose the zone identity and current restore permission."""
        zone = self.coordinator.data.zones.get(self.zone_id)
        return {
            "zone_id": self.zone_id,
            "restore_allowed": None if zone is None else zone.restore_allowed,
        }

    async def async_press(self) -> None:
        """Restore the zone using validated FlexC action 4."""
        await self.coordinator.async_restore_zone(self.zone_id)


class SpcDoorActionButton(
    CoordinatorEntity[SpcFlexCZoneControlCoordinator], ButtonEntity
):
    """Represent one momentary SPC door-control action."""

    _attr_has_entity_name = True
    entity_description: SpcDoorButtonDescription

    def __init__(
        self,
        coordinator: SpcFlexCZoneControlCoordinator,
        door_id: int,
        description: SpcDoorButtonDescription,
    ) -> None:
        """Initialize a door action button."""
        super().__init__(coordinator)
        self.door_id = door_id
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_door_{door_id}_{description.key}"
        )
        self._attr_device_info = build_door_device_info(coordinator, door_id)

    @property
    def available(self) -> bool:
        """Return whether the discovered door is currently known."""
        return self.door_id in self.coordinator.data.doors

    async def async_press(self) -> None:
        """Send the Vanderbilt SPCLink-proven door action."""
        await self.coordinator.async_control_door(
            self.door_id, self.entity_description.action
        )


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up action buttons for dynamically discovered SPC doors."""
    coordinator: SpcFlexCZoneControlCoordinator = entry.runtime_data
    known_doors: set[int] = set()
    known_zones: set[int] = set()

    def add_buttons() -> None:
        """Create restore and door-action buttons for discovered objects."""
        entities: list[ButtonEntity] = []
        for zone_id in coordinator.data.zones:
            if zone_id in known_zones:
                continue
            known_zones.add(zone_id)
            entities.append(SpcZoneRestoreButton(coordinator, zone_id))

        for door_id in coordinator.data.doors:
            if door_id in known_doors:
                continue
            known_doors.add(door_id)
            entities.extend(
                SpcDoorActionButton(coordinator, door_id, description)
                for description in DOOR_BUTTONS
            )
        if entities:
            async_add_entities(entities)

    add_buttons()
    entry.async_on_unload(coordinator.async_add_listener(add_buttons))
