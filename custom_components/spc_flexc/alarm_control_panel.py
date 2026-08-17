from typing import Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .coordinator import SpcFlexCCoordinator

MODE_LABELS: dict[int, str] = {
    0: "Unset",
    1: "Set",
    2: "PartSetA",
    3: "PartSetB",
}


class SpcAreaAlarmControlPanel(
    CoordinatorEntity[SpcFlexCCoordinator],
    AlarmControlPanelEntity,
):
    """Represent one SPC area."""

    _attr_has_entity_name = True
    _attr_code_arm_required = False
    _attr_supported_features = AlarmControlPanelEntityFeature(0)

    def __init__(
        self,
        coordinator: SpcFlexCCoordinator,
        area_id: int,
    ) -> None:
        super().__init__(coordinator)

        self.area_id = area_id

        area = coordinator.data.areas[area_id]

        self._attr_name = area.name or f"Area {area_id}"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_area_{area_id}"

    @property
    def available(self) -> bool:
        """Return whether the last known area exists."""
        return self.area_id in self.coordinator.data.areas

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the SPC area operating state."""
        area = self.coordinator.data.areas.get(self.area_id)

        if area is None or area.mode is None:
            return None

        if area.mode == 0:
            return AlarmControlPanelState.DISARMED

        if area.mode == 1:
            return AlarmControlPanelState.ARMED_AWAY

        if area.mode == 2:
            return AlarmControlPanelState.ARMED_HOME

        if area.mode == 3:
            return AlarmControlPanelState.ARMED_NIGHT

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return SPC-specific area attributes."""
        area = self.coordinator.data.areas.get(self.area_id)

        if area is None:
            return {}

        return {
            "area_id": area.area_id,
            "mode": area.mode,
            "mode_name": (
                MODE_LABELS.get(area.mode) if area.mode is not None else None
            ),
            "partset_a_enabled": area.partset_a_enabled,
            "partset_b_enabled": area.partset_b_enabled,
            "last_set_time": area.last_set_time,
            "last_set_user_id": area.last_set_user_id,
            "last_set_user_name": area.last_set_user_name,
            "last_unset_time": area.last_unset_time,
            "last_unset_user_id": area.last_unset_user_id,
            "last_unset_user_name": area.last_unset_user_name,
            "last_alarm": area.last_alarm,
            "internal_bells": area.internal_bells,
            "external_bells": area.external_bells,
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up dynamically discovered SPC areas."""
    coordinator: SpcFlexCCoordinator = entry.runtime_data

    known_areas: set[int] = set()

    def add_area_entities() -> None:
        entities: list[SpcAreaAlarmControlPanel] = []

        for area_id in sorted(coordinator.data.areas):
            if area_id in known_areas:
                continue

            known_areas.add(area_id)

            entities.append(
                SpcAreaAlarmControlPanel(
                    coordinator,
                    area_id,
                )
            )

        if entities:
            async_add_entities(entities)

    add_area_entities()

    entry.async_on_unload(coordinator.async_add_listener(add_area_entities))
