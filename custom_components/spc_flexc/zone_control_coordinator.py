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
from .flexc.connection import FlexCCommandTimeout, FlexCError
from .flexc.flexml import (
    FlexMLError,
    build_door_control_command,
    build_door_status_batch,
    parse_door_control,
    parse_door_status,
)
from .flexc.read_retry import async_retry_read_once
from .flexc.zone_control import async_set_zone_inhibited, async_set_zone_isolated
from .models import DoorState

_LOGGER = logging.getLogger(__name__)
DOOR_ACTIONS = {5, 6, 7, 8}
# Persistent door actions empirically validated against SPC door MODE values.
# Action 5 is a transient pulse and deliberately has no verifiable target mode.
DOOR_ACTION_TARGET_MODES = {6: 2, 7: 0, 8: 1}
DOOR_PERSISTENT_MODES = frozenset(DOOR_ACTION_TARGET_MODES.values())
ZONE_CONTROL_VERIFY_ATTEMPTS = 3
ZONE_CONTROL_VERIFY_DELAY = 0.25


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
        except asyncio.CancelledError:
            _LOGGER.warning(
                "SPC door polling cancelled: entry_state=%s hass_state=%s discovery_requested=%s",
                self.entry.state,
                self.hass.state,
                self._discovery_requested,
            )
            raise
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

    async def _async_reconcile_known_state_locked(self) -> bool:
        """Extend reconnect reconciliation with current door state."""
        changed = await super()._async_reconcile_known_state_locked()
        if not self._door_discovery_complete or not self._detected_door_ids:
            return changed

        door_ids = sorted(self._detected_door_ids)
        command = build_door_status_batch(
            door_ids, self.client.command_username, self.client.command_password
        )
        response = await async_retry_read_once(
            lambda: self.client.async_send_flexml(command),
            description="reconciling doors after reconnect",
        )
        raw_doors = parse_door_status(response)
        for raw_door in raw_doors:
            door_id = int(raw_door["DOOR_ID"])
            previous = self.state.doors.get(door_id)
            previous_mode = None if previous is None else previous.mode
            door = _door_state_from_status(raw_door)
            if previous is None or previous.raw != door.raw:
                _LOGGER.info(
                    "Door %d reconciliation changed state after reconnect: "
                    "MODE=%s -> %s",
                    door_id,
                    previous_mode,
                    door.mode,
                )
                changed = True
            self.state.doors[door_id] = door
        return changed

    async def async_control_door(self, door_id: int, action: int) -> None:
        """Send one validated door action and verify/recover persistent modes."""
        if door_id not in self.state.doors:
            raise ValueError(f"Unknown SPC door {door_id}")
        if action not in DOOR_ACTIONS:
            raise ValueError(f"Unsupported SPC door action {action}")

        loop = asyncio.get_running_loop()
        requested_at = loop.time()
        _LOGGER.info(
            "Door %d control entered: action=%d connected=%s",
            door_id,
            action,
            self.client.connected,
        )
        async with self._client_operation_lock:
            lock_acquired_at = loop.time()
            _LOGGER.info(
                "Door %d operation lock acquired after %.3fs: action=%d connected=%s",
                door_id,
                lock_acquired_at - requested_at,
                action,
                self.client.connected,
            )
            await self.client.async_ensure_connected()
            connection_ready_at = loop.time()
            _LOGGER.info(
                "Door %d FlexC connection ready after %.3fs (total %.3fs): action=%d",
                door_id,
                connection_ready_at - lock_acquired_at,
                connection_ready_at - requested_at,
                action,
            )
            command = build_door_control_command(
                door_id,
                action,
                self.client.command_username,
                self.client.command_password,
            )
            status_command = build_door_status_batch(
                [door_id], self.client.command_username, self.client.command_password
            )
            _LOGGER.info("Door %d control requested: action=%d", door_id, action)
            control_timed_out = False
            try:
                response = await self.client.async_send_flexml(command)
                parse_door_control(response)
                _LOGGER.info(
                    "Door %d control accepted by SPC: action=%d", door_id, action
                )
            except FlexCCommandTimeout:
                control_timed_out = True
                _LOGGER.warning(
                    "Door %d control timed out; recovering FlexC session (action=%d)",
                    door_id,
                    action,
                )
                await self.client.async_recover_session()

            if control_timed_out:
                status_response = await async_retry_read_once(
                    lambda: self.client.async_send_flexml(status_command),
                    description=f"checking door {door_id} after timeout",
                )
            else:
                try:
                    status_response = await async_retry_read_once(
                        lambda: self.client.async_send_flexml(status_command),
                        description=f"refreshing door {door_id} after control",
                    )
                except FlexCCommandTimeout:
                    _LOGGER.warning(
                        "Door %d verification timed out after SPC accepted action "
                        "%d; recovering FlexC session",
                        door_id,
                        action,
                    )
                    await self.client.async_recover_session()
                    status_response = await async_retry_read_once(
                        lambda: self.client.async_send_flexml(status_command),
                        description=f"checking door {door_id} after verification timeout",
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
            refreshed = self.state.doors[door_id]

            _LOGGER.info(
                "Door %d status after action %d: STATUS=%s MODE=%s "
                "DPS_INPUT=%s DRS_INPUT=%s",
                door_id,
                action,
                refreshed.status,
                refreshed.mode,
                refreshed.dps_input,
                refreshed.drs_input,
            )

            if not control_timed_out:
                return

            target_mode = DOOR_ACTION_TARGET_MODES.get(action)
            if target_mode is None:
                _LOGGER.warning(
                    "Door %d transient action %d was not retried after timeout; "
                    "door MODE cannot prove whether the pulse was already executed",
                    door_id,
                    action,
                )
                return

            if refreshed.mode == target_mode:
                _LOGGER.info(
                    "Door %d action %d confirmed after timeout: MODE=%d; "
                    "control will not be replayed",
                    door_id,
                    action,
                    target_mode,
                )
                return

            if refreshed.mode not in DOOR_PERSISTENT_MODES:
                _LOGGER.error(
                    "Door %d outcome is unknown after timeout: action=%d "
                    "expected MODE=%d current MODE=%s; control was not retried",
                    door_id,
                    action,
                    target_mode,
                    refreshed.mode,
                )
                raise ValueError(
                    f"SPC door {door_id} mode is unknown after control recovery"
                )

            _LOGGER.warning(
                "Door %d remains MODE=%s while action %d requires MODE=%d; "
                "retrying control once",
                door_id,
                refreshed.mode,
                action,
                target_mode,
            )
            response = await self.client.async_send_flexml(command)
            parse_door_control(response)
            _LOGGER.info(
                "Door %d retry accepted by SPC for action %d; verifying final status",
                door_id,
                action,
            )
            status_response = await async_retry_read_once(
                lambda: self.client.async_send_flexml(status_command),
                description=f"refreshing door {door_id} after retry",
            )
            raw_doors = parse_door_status(status_response)
            if not raw_doors or int(raw_doors[0].get("DOOR_ID", -1)) != door_id:
                raise ValueError(
                    f"SPC door {door_id} returned invalid status after control retry"
                )
            self._update_door_states(raw_doors)
            self.async_set_updated_data(self.state)
            refreshed = self.state.doors[door_id]
            if refreshed.mode != target_mode:
                raise ValueError(
                    f"SPC door {door_id} did not confirm MODE={target_mode} "
                    "after control retry"
                )
            _LOGGER.info(
                "Door %d final status confirmed after retry: action=%d MODE=%d",
                door_id,
                action,
                target_mode,
            )

    def _update_zone_from_control_status(
        self, zone_id: int, raw_zone: dict[str, str]
    ) -> None:
        """Update one existing zone from a post-control status response."""
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

    async def _async_refresh_zone_after_control(
        self, zone_id: int, *, expected_attribute: str, expected_state: bool
    ) -> None:
        """Refresh until SPC explicitly confirms a requested zone state."""
        for attempt in range(ZONE_CONTROL_VERIFY_ATTEMPTS):
            if attempt:
                await asyncio.sleep(ZONE_CONTROL_VERIFY_DELAY)
            raw_zones = await async_retry_read_once(
                lambda: self.client.async_get_zone_status([zone_id]),
                description=f"refreshing zone {zone_id} after control",
            )
            if not raw_zones:
                continue
            raw_zone = raw_zones[0]
            if int(raw_zone["ZONE_ID"]) != zone_id:
                raise ValueError(
                    f"SPC returned zone {raw_zone.get('ZONE_ID')} while refreshing zone {zone_id}"
                )
            self._update_zone_from_control_status(zone_id, raw_zone)
            if getattr(self.state.zones[zone_id], expected_attribute) is expected_state:
                self.async_set_updated_data(self.state)
                return

        self.async_set_updated_data(self.state)
        raise ValueError(
            f"SPC zone {zone_id} did not confirm the requested {expected_attribute} state"
        )

    async def async_set_zone_inhibited(self, zone_id: int, inhibited: bool) -> None:
        """Set zone inhibition after checking the explicit SPC permission."""
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
            await self._async_refresh_zone_after_control(
                zone_id, expected_attribute="inhibited", expected_state=inhibited
            )

    async def async_set_zone_isolated(self, zone_id: int, isolated: bool) -> None:
        """Set zone isolation after checking the explicit SPC permission."""
        zone = self.state.zones.get(zone_id)
        if zone is None:
            raise ValueError(f"Unknown SPC zone {zone_id}")
        if isolated:
            if zone.isolated is True:
                return
            if zone.isolate_allowed is not True:
                raise ValueError(
                    f"SPC zone {zone_id} does not currently allow isolation"
                )
        else:
            if zone.isolated is False:
                return
            if zone.deisolate_allowed is not True:
                raise ValueError(
                    f"SPC zone {zone_id} does not currently allow de-isolation"
                )

        async with self._client_operation_lock:
            await self.client.async_ensure_connected()
            await async_set_zone_isolated(self.client, zone_id, isolated)
            await self._async_refresh_zone_after_control(
                zone_id, expected_attribute="isolated", expected_state=isolated
            )

    async def async_inhibit_zone(self, zone_id: int) -> None:
        """Inhibit one SPC zone using the validated FlexC command."""
        await self.async_set_zone_inhibited(zone_id, True)

    async def async_deinhibit_zone(self, zone_id: int) -> None:
        """De-inhibit one SPC zone using the validated FlexC command."""
        await self.async_set_zone_inhibited(zone_id, False)

    async def async_isolate_zone(self, zone_id: int) -> None:
        """Isolate one SPC zone using the validated FlexC command."""
        await self.async_set_zone_isolated(zone_id, True)

    async def async_deisolate_zone(self, zone_id: int) -> None:
        """De-isolate one SPC zone using the validated FlexC command."""
        await self.async_set_zone_isolated(zone_id, False)

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
