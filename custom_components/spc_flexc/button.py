"""Button entities for SPC FlexC access-control door actions."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .flexc.device import build_door_device_info
from .zone_control_coordinator import SpcFlexCZoneControlCoordinator


@dataclass(frozen=True, kw_only=True)
class SpcDoorButtonDescription(ButtonEntityDescription):
    """Describe one SPC FlexC door action button."""

    action: int


DOOR_BUTTONS = (
    SpcDoorButtonDescription(key="open_momentarily", translation_key="open_momentarily", action=5),
    SpcDoorButtonDescription(key="open_permanently", translation_key="open_permanently", action=6),
    SpcDoorButtonDescription(key="set_normal", translation_key="set_normal", action=7),
    SpcDoorButtonDescription(key="lock", translation_key="lock", action=8),
)


class SpcDoorActionButton(CoordinatorEntity[SpcFlexCZoneControlCoordinator], ButtonEntity):
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

    def add_door_buttons() -> None:
        """Create the four action buttons for newly discovered doors."""
        entities: list[ButtonEntity] = []
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

    add_door_buttons()

    def coordinator_updated() -> None:
        """Handle doors discovered after platform setup."""
        add_door_buttons()

    entry.async_on_unload(coordinator.async_add_listener(coordinator_updated))
