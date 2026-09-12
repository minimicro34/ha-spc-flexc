"""Zone-control and door-status coordinator extensions for SPC FlexC."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import UTC, datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOOR_POLL_INTERVAL, DOOR_POLL_PHASE
from .coordinator import SpcFlexCCoordinator, poll_delay_for_phase
from .flexc.connection import FlexCError
from .flexc.flexml import (
    FlexMLError,
    build_door_control_command,
    build_door_status_batch,
    parse_door_control,
    parse_door_status,
)
from .flexc.read_retry import async_retry_read_once
from .flexc.zone_control import async_set_zone_inhibited
from .models import DoorState

_LOGGER = logging.getLogger(__name__)
DOOR_ACTIONS = {5, 6, 7, 8}


class SpcFlexCZoneControlCoordinator(SpcFlexCCoordinator):
    """SPC coordinator with validated zone control and live door status."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize SPC zone-control and door-status extensions."""
        super().__init__(hass, entry)
        self._door_poll_task: asyncio.Task[None] | None = None

    async def _async_discover_panel_objects(self) -> None:
        """Run standard discovery and start polling any detected doors."""
        await super()._async_discover_panel_objects()
        self._schedule_door_polling()

    def _schedule_door_polling(self) -> None:
        """Start periodic status polling for discovered access-control doors."""
        if not self._door_discovery_complete or not self._detected_door_ids:
            return
        if self._door_poll_task is not None and not self._door_poll_task.done():
            return
        self._door_poll_task = self.entry.async_create_background_task(
            self.hass,
            self._async_door_poll_loop(),
            name="spc_flexc door polling",
            eager_start=False,
        )

    async def _async_door_poll_loop(self) -> None:
        """Poll discovered doors without interpreting undocumented mode values."""
        _LOGGER.debug("SPC door polling started")
        try:
            while True:
                await asyncio.sleep(
                    poll_delay_for_phase(DOOR_POLL_PHASE, DOOR_POLL_INTERVAL)
                )
                if not self._door_discovery_complete:
                    continue
                door_ids = sorted(self._detected_door_ids)
                if not door_ids:
                    continue
                try:
                    raw_doors = await self._async_read_doors(door_ids)
                    if self._update_door_states(raw_doors):
                        self.async_set_updated_data(self.state)
                except asyncio.CancelledError:
                    raise
                except (FlexCError, FlexMLError) as err:
                    _LOGGER.debug("SPC door polling failed: %s", err)
                except Exception:
                    _LOGGER.exception(
                        "Unexpected error while polling SPC doors; polling will continue"
                    )
        finally:
            _LOGGER.debug("SPC door polling stopped")
            current_task = asyncio.current_task()
            if self._door_poll_task is current_task:
                self._door_poll_task = None
                if self._discovery_requested:
                    _LOGGER.warning("SPC door polling stopped unexpectedly; restarting")
                    self._schedule_door_polling()

    async def _async_read_doors(self, door_ids: list[int]) -> list[dict[str, str]]:
        """Read current FlexC status for the requested doors."""
        async with self._client_operation_lock:
            await self.client.async_ensure_connected()
            command = build_door_status_batch(
                door_ids, self.client.command_username, self.client.command_password
            )
            response = await async_retry_read_once(
                lambda: self.client.async_send_flexml(command),
                description="reading door status",
            )
        return parse_door_status(response)

    def _update_door_states(self, raw_doors: list[dict[str, str]]) -> bool:
        """Store raw door states and return whether anything changed."""
        changed = False
        for raw_door in raw_doors:
            door = _door_state_from_status(raw_door)
            previous = self.state.doors.get(door.door_id)
            if previous is None or previous.raw != door.raw:
                changed = True
            self.state.doors[door.door_id] = door
        return changed

    async def async_control_door(self, door_id: int, action: int) -> None:
        """Send one SPCLink-proven door action and immediately refresh status."""
        if door_id not in self.state.doors:
            raise ValueError(f"Unknown SPC door {door_id}")
        if action not in DOOR_ACTIONS:
            raise ValueError(f"Unsupported SPC door action {action}")

        async with self._client_operation_lock:
            await self.client.async_ensure_connected()
            command = build_door_control_command(
                door_id,
                action,
                self.client.command_username,
                self.client.command_password,
            )
            response = await self.client.async_send_flexml(command)
            parse_door_control(response)
            status_command = build_door_status_batch(
                [door_id], self.client.command_username, self.client.command_password
            )
            status_response = await async_retry_read_once(
                lambda: self.client.async_send_flexml(status_command),
                description=f"refreshing door {door_id} after control",
            )

        raw_doors = parse_door_status(status_response)
        if not raw_doors:
            raise ValueError(f"SPC door {door_id} returned no status after control")
        if int(raw_doors[0]["DOOR_ID"]) != door_id:
            raise ValueError(
                f"SPC returned door {raw_doors[0].get('DOOR_ID')} while refreshing door {door_id}"
            )
        self._update_door_states(raw_doors)
        self.async_set_updated_data(self.state)

    async def async_set_zone_inhibited(self, zone_id: int, inhibited: bool) -> None:
        """Set zone inhibition and refresh the zone state immediately."""
        zone = self.state.zones.get(zone_id)
        if zone is None:
            raise ValueError(f"Unknown SPC zone {zone_id}")
        if inhibited:
            if zone.inhibited is True:
                return
            if zone.inhibit_allowed is not True:
                raise ValueError(
                    f"SPC zone {zone_id} does not currently allow inhibition"
                )
        else:
            if zone.inhibited is False:
                return
            if zone.deinhibit_allowed is not True:
                raise ValueError(
                    f"SPC zone {zone_id} does not currently allow de-inhibition"
                )

        async with self._client_operation_lock:
            await self.client.async_ensure_connected()
            await async_set_zone_inhibited(self.client, zone_id, inhibited)
            raw_zones = await async_retry_read_once(
                lambda: self.client.async_get_zone_status([zone_id]),
                description=f"refreshing zone {zone_id} after inhibition control",
            )

        if not raw_zones:
            raise ValueError(f"SPC zone {zone_id} returned no status after control")
        raw_zone = raw_zones[0]
        if int(raw_zone["ZONE_ID"]) != zone_id:
            raise ValueError(
                f"SPC returned zone {raw_zone.get('ZONE_ID')} while refreshing zone {zone_id}"
            )

        refreshed = self.state.zones[zone_id]
        refreshed.name = raw_zone.get("ZONE_NAME")
        refreshed.area_id = _int_or_none(raw_zone.get("AREA_ID"))
        refreshed.area_name = raw_zone.get("AREA_NAME")
        refreshed.zone_type = _int_or_none(raw_zone.get("TYPE"))
        refreshed.input_state = _int_or_none(raw_zone.get("INPUT"))
        refreshed.logic_input = _int_or_none(raw_zone.get("LOGIC_INPUT"))
        refreshed.status = _int_or_none(raw_zone.get("STATUS"))
        refreshed.proc_state = _int_or_none(raw_zone.get("PROC_STATE"))
        refreshed.alarm_state = _int_or_none(raw_zone.get("ALARM_STATE"))
        refreshed.inhibit_allowed = _bool_or_none(raw_zone.get("INHIBIT_ALLOWED"))
        refreshed.isolate_allowed = _bool_or_none(raw_zone.get("ISOLATE_ALLOWED"))
        refreshed.actuations_since_last_read = _int_or_none(
            raw_zone.get("ACTUATIONS_SINCE_LAST_READ")
        )
        refreshed.raw = dict(raw_zone)
        refreshed.updated_at = datetime.now(UTC)

        if refreshed.inhibited is not inhibited:
            raise ValueError(
                f"SPC zone {zone_id} did not confirm the requested inhibition state"
            )
        self.async_set_updated_data(self.state)

    async def async_inhibit_zone(self, zone_id: int) -> None:
        """Inhibit one SPC zone using the validated FlexC command."""
        await self.async_set_zone_inhibited(zone_id, True)

    async def async_deinhibit_zone(self, zone_id: int) -> None:
        """De-inhibit one SPC zone using the validated FlexC command."""
        await self.async_set_zone_inhibited(zone_id, False)

    async def async_shutdown(self) -> None:
        """Stop door polling and shut down the base coordinator."""
        self._discovery_requested = False
        door_task = self._door_poll_task
        self._door_poll_task = None
        if door_task is not None and not door_task.done():
            door_task.cancel()
            with suppress(asyncio.CancelledError):
                await door_task
        await super().async_shutdown()


def _door_state_from_status(raw_door: dict[str, str]) -> DoorState:
    """Build a door state while preserving all raw FlexC values."""
    return DoorState(
        door_id=int(raw_door["DOOR_ID"]),
        name=raw_door.get("DOOR_NAME")
        or raw_door.get("NAME")
        or raw_door.get("ZONE_NAME"),
        status=_int_or_none(raw_door.get("STATUS")),
        mode=_int_or_none(raw_door.get("DOOR_MODE") or raw_door.get("MODE")),
        dps_input=_int_or_none(raw_door.get("DPS_INPUT")),
        drs_input=_int_or_none(raw_door.get("DRS_INPUT")),
        reader1_format=_int_or_none(raw_door.get("READER1_FORMAT")),
        reader2_format=_int_or_none(raw_door.get("READER2_FORMAT")),
        zone_id=_int_or_none(raw_door.get("ZONE_ID")),
        zone_name=raw_door.get("ZONE_NAME"),
        area_id=_int_or_none(raw_door.get("AREA_ID")),
        area_name=raw_door.get("AREA_NAME"),
        area_side_1=_int_or_none(raw_door.get("AREA_SIDE_1")),
        area_side_1_name=raw_door.get("AREA_SIDE_1_NAME"),
        entry_exit=_bool_or_none(raw_door.get("ENTRY_EXIT")),
        normal_allowed=_bool_or_none(raw_door.get("NORMAL_ALLOWED")),
        lock_allowed=_bool_or_none(raw_door.get("LOCK_ALLOWED")),
        raw=dict(raw_door),
        updated_at=datetime.now(UTC),
    )


def _int_or_none(value: object) -> int | None:
    """Convert a FlexC scalar to int when possible."""
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: object) -> bool | None:
    """Convert a FlexC 0/1 scalar to bool when possible."""
    if value is None:
        return None
    text = str(value).strip()
    if text == "0":
        return False
    if text == "1":
        return True
    return None
