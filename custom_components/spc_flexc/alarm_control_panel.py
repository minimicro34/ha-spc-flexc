import xml.etree.ElementTree as ET
from typing import Any
from xml.sax.saxutils import quoteattr

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .const import (
    CONF_COMMAND_PASSWORD,
    CONF_COMMAND_USERNAME,
)
from .coordinator import SpcFlexCCoordinator
from .flexc.device import build_area_device_info

MODE_LABELS: dict[int, str] = {
    0: "Unset",
    1: "PartSetA",
    2: "PartSetB",
    3: "Set",
}

MODE_UNSET = 0
MODE_PARTSET_A = 1
MODE_PARTSET_B = 2
MODE_SET = 3


def _flexml_envelope(
    username: str,
    password: str,
    body: str,
) -> str:
    """Build one authenticated FLEXML command."""
    return (
        '<FLEXML_CMD VER="1.0" '
        f"PANEL_USERNAME={quoteattr(username)} "
        f"PANEL_PASSWORD={quoteattr(password)}>"
        f"{body}"
        "</FLEXML_CMD>"
    )


def _reply_is_ok(
    xml_text: str,
    reply_tag: str,
) -> bool:
    """Return whether a FLEXML reply reports protocol success."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return False

    reply = root.find(reply_tag)

    return (
        reply is not None
        and reply.get("RESULT") == "0"
        and reply.get("CMD_RESULT") == "OK"
    )


class SpcAreaAlarmControlPanel(
    CoordinatorEntity[SpcFlexCCoordinator],
    AlarmControlPanelEntity,
):
    """Represent one SPC area."""

    _attr_has_entity_name = True
    _attr_code_arm_required = False

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
        self._attr_device_info = build_area_device_info(
            coordinator,
            area_id,
        )

    @property
    def available(self) -> bool:
        """Return whether the last known area exists."""
        return self.area_id in self.coordinator.data.areas

    @property
    def supported_features(self) -> AlarmControlPanelEntityFeature:
        """Return supported alarm features."""
        area = self.coordinator.data.areas.get(self.area_id)

        features = AlarmControlPanelEntityFeature.ARM_AWAY

        if area is not None and area.partset_a_enabled:
            features |= AlarmControlPanelEntityFeature.ARM_HOME

        if area is not None and area.partset_b_enabled:
            features |= AlarmControlPanelEntityFeature.ARM_NIGHT

        return features

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the SPC area operating state."""
        area = self.coordinator.data.areas.get(self.area_id)

        if area is None or area.mode is None:
            return None

        if area.mode == MODE_UNSET:
            return AlarmControlPanelState.DISARMED

        if area.mode == MODE_PARTSET_A:
            return AlarmControlPanelState.ARMED_HOME

        if area.mode == MODE_PARTSET_B:
            return AlarmControlPanelState.ARMED_NIGHT

        if area.mode == MODE_SET:
            return AlarmControlPanelState.ARMED_AWAY

        return None

    async def _async_change_mode(
        self,
        mode: int,
    ) -> None:
        """Request one SPC area mode change."""
        area = self.coordinator.data.areas.get(self.area_id)

        if area is None:
            raise HomeAssistantError(f"SPC area {self.area_id} is not available")

        if mode == MODE_PARTSET_A and not area.partset_a_enabled:
            raise HomeAssistantError(
                f"SPC area {self.area_id} does not support Part Set A"
            )

        if mode == MODE_PARTSET_B and not area.partset_b_enabled:
            raise HomeAssistantError(
                f"SPC area {self.area_id} does not support Part Set B"
            )

        username = self.coordinator.entry.data[CONF_COMMAND_USERNAME]
        password = self.coordinator.entry.data[CONF_COMMAND_PASSWORD]

        precheck_body = (
            "<CMD_GET_AREA_CHANGE_MODE_STATUS "
            f'AREA_ID="{self.area_id}" MODE="{mode}" />'
        )

        command_body = (
            f'<CMD_AREA_CHANGE_MODE AREA_ID="{self.area_id}" MODE="{mode}" />'
        )

        # The coordinator and entities share one FlexC connection.
        # Serialize this complete command sequence with normal polling.
        async with self.coordinator._client_operation_lock:
            await self.coordinator.client.async_ensure_connected()

            precheck_reply = await self.coordinator.client.async_send_flexml(
                _flexml_envelope(
                    username,
                    password,
                    precheck_body,
                )
            )

            if not _reply_is_ok(
                precheck_reply,
                "REPLY_GET_AREA_CHANGE_MODE_STATUS",
            ):
                raise HomeAssistantError(
                    f"SPC refused area mode precheck: {precheck_reply}"
                )

            # IMPORTANT:
            # This state-changing command is intentionally sent exactly once.
            # Never automatically retry it after an exception or timeout.
            command_reply = await self.coordinator.client.async_send_flexml(
                _flexml_envelope(
                    username,
                    password,
                    command_body,
                )
            )

            if not _reply_is_ok(
                command_reply,
                "REPLY_AREA_CHANGE_MODE",
            ):
                raise HomeAssistantError(
                    f"SPC refused area mode change: {command_reply}"
                )

        # Refresh only after releasing the FlexC operation lock.
        # A refresh failure must never cause the state-changing command
        # above to be resent.
        await self.coordinator.async_request_refresh()

    async def async_alarm_disarm(
        self,
        code: str | None = None,
    ) -> None:
        """Disarm the SPC area."""
        await self._async_change_mode(MODE_UNSET)

    async def async_alarm_arm_away(
        self,
        code: str | None = None,
    ) -> None:
        """Full-set the SPC area."""
        await self._async_change_mode(MODE_SET)

    async def async_alarm_arm_home(
        self,
        code: str | None = None,
    ) -> None:
        """Part-set A the SPC area."""
        await self._async_change_mode(MODE_PARTSET_A)

    async def async_alarm_arm_night(
        self,
        code: str | None = None,
    ) -> None:
        """Part-set B the SPC area."""
        await self._async_change_mode(MODE_PARTSET_B)

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
