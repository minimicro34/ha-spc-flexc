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
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_COMMAND_PASSWORD,
    CONF_COMMAND_USERNAME,
    DOMAIN,
)
from .coordinator import SpcFlexCCoordinator
from .flexc.connection import FlexCError
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

REASON_ENGINEER_MODE = "10006"
ZONE_REASON_BASE = 1000


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


def _get_area_change_mode_reason(
    xml_text: str,
    area_id: int,
) -> str | None:
    """Return the first SPC reason preventing an area mode change."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    reply = root.find("REPLY_GET_AREA_CHANGE_MODE_STATUS")
    if reply is None or reply.get("RESULT") != "0" or reply.get("CMD_RESULT") != "OK":
        return None

    status = reply.find("AREA_CHANGE_MODE_STATUS")
    if status is None or status.get("AREA_ID") != str(area_id):
        return None

    return status.get("REASON_0")


def _area_name(
    coordinator: SpcFlexCCoordinator,
    area_id: int,
) -> str:
    """Return a friendly SPC area name."""
    area = coordinator.data.areas.get(area_id)
    if area is not None and area.name:
        return area.name
    return f"Area {area_id}"


def _active_blocking_faults(
    coordinator: SpcFlexCCoordinator,
) -> list[str]:
    """Return known active panel faults that may explain a not-ready area."""

    faults = coordinator.data.faults
    active: list[str] = []

    if faults.mains_fault is True:
        active.append("230 V mains fault")

    if faults.battery_fault is True:
        active.append("panel battery fault")

    if faults.panel_tamper is True:
        active.append("panel tamper")

    return active


def _raise_not_ready(
    coordinator: SpcFlexCCoordinator,
    area_id: int,
    reason: str,
) -> None:
    """Raise a translated user-facing SPC not-ready error."""
    area_name = _area_name(coordinator, area_id)

    if reason == "2007":
        active_faults = _active_blocking_faults(coordinator)

        if active_faults:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="area_not_ready_faults",
                translation_placeholders={
                    "area": area_name,
                    "reason": reason,
                    "faults": ", ".join(active_faults),
                },
            )

        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="area_not_ready",
            translation_placeholders={
                "area": area_name,
                "reason": reason,
            },
        )

    if reason == REASON_ENGINEER_MODE:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="area_not_ready_engineer",
            translation_placeholders={
                "area": area_name,
                "reason": reason,
            },
        )

    try:
        reason_value = int(reason)
    except ValueError:
        reason_value = -1

    zone_id = reason_value - ZONE_REASON_BASE
    zone = coordinator.data.zones.get(zone_id) if zone_id > 0 else None

    if zone is not None:
        zone_name = getattr(zone, "name", None) or f"Zone {zone_id}"
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="area_not_ready_zone",
            translation_placeholders={
                "area": area_name,
                "zone": zone_name,
                "zone_id": str(zone_id),
                "reason": reason,
            },
        )

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="area_not_ready",
        translation_placeholders={
            "area": area_name,
            "reason": reason,
        },
    )


async def _async_precheck_area_mode(
    coordinator: SpcFlexCCoordinator,
    area_id: int,
    mode: int,
    username: str,
    password: str,
) -> None:
    """Check whether one SPC area can change to the requested mode."""
    body = f'<CMD_GET_AREA_CHANGE_MODE_STATUS AREA_ID="{area_id}" MODE="{mode}" />'
    reply = await coordinator.client.async_send_flexml(
        _flexml_envelope(username, password, body)
    )

    if not _reply_is_ok(reply, "REPLY_GET_AREA_CHANGE_MODE_STATUS"):
        raise HomeAssistantError(f"SPC refused area mode precheck: {reply}")

    reason = _get_area_change_mode_reason(reply, area_id)
    if reason is None:
        raise HomeAssistantError(f"Invalid SPC area mode precheck response: {reply}")

    if reason != "0":
        _raise_not_ready(coordinator, area_id, reason)


async def _async_send_area_mode_once(
    coordinator: SpcFlexCCoordinator,
    area_id: int,
    mode: int,
    username: str,
    password: str,
) -> None:
    """Send one state-changing area command exactly once."""
    body = f'<CMD_AREA_CHANGE_MODE AREA_ID="{area_id}" MODE="{mode}" />'

    # Never retry this state-changing command automatically.
    reply = await coordinator.client.async_send_flexml(
        _flexml_envelope(username, password, body)
    )

    if not _reply_is_ok(reply, "REPLY_AREA_CHANGE_MODE"):
        raise HomeAssistantError(f"SPC refused area mode change: {reply}")


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

    async def _async_change_mode(self, mode: int) -> None:
        """Request one SPC area mode change."""
        area = self.coordinator.data.areas.get(self.area_id)

        if area is None:
            raise HomeAssistantError(f"SPC area {self.area_id} is not available")

        if mode == MODE_PARTSET_A and not area.partset_a_enabled:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="partset_a_not_supported",
                translation_placeholders={
                    "area": area.name or f"Area {self.area_id}",
                },
            )

        if mode == MODE_PARTSET_B and not area.partset_b_enabled:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="partset_b_not_supported",
                translation_placeholders={
                    "area": area.name or f"Area {self.area_id}",
                },
            )

        username = self.coordinator.entry.data[CONF_COMMAND_USERNAME]
        password = self.coordinator.entry.data[CONF_COMMAND_PASSWORD]

        async with self.coordinator._client_operation_lock:
            await self.coordinator.client.async_ensure_connected()
            await _async_precheck_area_mode(
                self.coordinator,
                self.area_id,
                mode,
                username,
                password,
            )
            await _async_send_area_mode_once(
                self.coordinator,
                self.area_id,
                mode,
                username,
                password,
            )

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


class SpcPanelAlarmControlPanel(
    CoordinatorEntity[SpcFlexCCoordinator],
    AlarmControlPanelEntity,
):
    """Represent the complete SPC panel across all discovered areas."""

    _attr_has_entity_name = True
    _attr_code_arm_required = False
    _attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY

    def __init__(self, coordinator: SpcFlexCCoordinator) -> None:
        super().__init__(coordinator)

        panel = coordinator.data.panel
        serial = panel.serial_number or coordinator.entry.entry_id

        self._attr_name = "Alarm"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_panel_alarm"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(serial))},
        }

    @property
    def available(self) -> bool:
        """Return whether panel and area data are available."""
        return bool(self.coordinator.data.areas)

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the aggregate SPC panel state."""
        modes = [
            area.mode
            for area in self.coordinator.data.areas.values()
            if area.mode is not None
        ]

        if not modes:
            return None

        if all(mode == MODE_UNSET for mode in modes):
            return AlarmControlPanelState.DISARMED

        if all(mode == MODE_SET for mode in modes):
            return AlarmControlPanelState.ARMED_AWAY

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return aggregate SPC panel details."""
        return {
            "areas": {
                str(area_id): {
                    "name": area.name or f"Area {area_id}",
                    "mode": area.mode,
                    "mode_name": (
                        MODE_LABELS.get(area.mode) if area.mode is not None else None
                    ),
                }
                for area_id, area in sorted(self.coordinator.data.areas.items())
            }
        }

    async def async_alarm_arm_away(
        self,
        code: str | None = None,
    ) -> None:
        """Full-set every discovered SPC area."""
        area_ids = sorted(self.coordinator.data.areas)
        if not area_ids:
            raise HomeAssistantError("No SPC areas are available")

        username = self.coordinator.entry.data[CONF_COMMAND_USERNAME]
        password = self.coordinator.entry.data[CONF_COMMAND_PASSWORD]

        sent_area_ids: list[int] = []
        command_error: FlexCError | HomeAssistantError | None = None

        async with self.coordinator._client_operation_lock:
            await self.coordinator.client.async_ensure_connected()

            # Precheck every area before sending the first SET command.
            for area_id in area_ids:
                await _async_precheck_area_mode(
                    self.coordinator,
                    area_id,
                    MODE_SET,
                    username,
                    password,
                )

            # All prechecks succeeded. Send each SET exactly once.
            for area_id in area_ids:
                try:
                    await _async_send_area_mode_once(
                        self.coordinator,
                        area_id,
                        MODE_SET,
                        username,
                        password,
                    )
                    sent_area_ids.append(area_id)
                except (FlexCError, HomeAssistantError) as err:
                    command_error = err
                    break

        # Refresh after releasing the FlexC lock. Never resend a SET because
        # refresh failed.
        await self.coordinator.async_request_refresh()

        if command_error is not None:
            armed_areas = (
                ", ".join(
                    _area_name(self.coordinator, area_id) for area_id in sent_area_ids
                )
                or "none"
            )

            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="global_arm_incomplete",
                translation_placeholders={
                    "areas": armed_areas,
                    "error": str(command_error),
                },
            ) from command_error

    async def async_alarm_disarm(
        self,
        code: str | None = None,
    ) -> None:
        """Unset every discovered SPC area."""
        area_ids = sorted(self.coordinator.data.areas)
        if not area_ids:
            raise HomeAssistantError("No SPC areas are available")

        username = self.coordinator.entry.data[CONF_COMMAND_USERNAME]
        password = self.coordinator.entry.data[CONF_COMMAND_PASSWORD]

        failed: list[str] = []

        async with self.coordinator._client_operation_lock:
            await self.coordinator.client.async_ensure_connected()

            # During global UNSET, failure on one area must not prevent an
            # attempt on the remaining areas. Each state change is still sent
            # at most once.
            for area_id in area_ids:
                try:
                    await _async_precheck_area_mode(
                        self.coordinator,
                        area_id,
                        MODE_UNSET,
                        username,
                        password,
                    )
                    await _async_send_area_mode_once(
                        self.coordinator,
                        area_id,
                        MODE_UNSET,
                        username,
                        password,
                    )
                except (FlexCError, HomeAssistantError) as err:
                    failed.append(f"{_area_name(self.coordinator, area_id)}: {err}")

        await self.coordinator.async_request_refresh()

        if failed:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="global_disarm_incomplete",
                translation_placeholders={
                    "errors": "; ".join(failed),
                },
            )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SPC panel and dynamically discovered SPC areas."""
    coordinator: SpcFlexCCoordinator = entry.runtime_data

    known_areas: set[int] = set()

    async_add_entities([SpcPanelAlarmControlPanel(coordinator)])

    def add_area_entities() -> None:
        entities: list[SpcAreaAlarmControlPanel] = []

        for area_id in sorted(coordinator.data.areas):
            if area_id in known_areas:
                continue

            known_areas.add(area_id)
            entities.append(SpcAreaAlarmControlPanel(coordinator, area_id))

        if entities:
            async_add_entities(entities)

    add_area_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_area_entities))
