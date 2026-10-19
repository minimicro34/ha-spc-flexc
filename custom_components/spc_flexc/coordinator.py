"""Data update coordinator for the SPC FlexC integration."""

import asyncio
import logging
from contextlib import suppress
from datetime import UTC, datetime, timedelta, tzinfo
from functools import partial
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    AREA_DISCOVERY_MAX_ID,
    ATS_IDS,
    CONF_USER_ALIASES,
    DEFAULT_PANEL_INTERVAL,
    DOMAIN,
    DOOR_DISCOVERY_MAX_ID,
    XBUS_POLL_INTERVAL,
    XBUS_POLL_PHASE,
    XBUS_TAMPER_INHIBIT_MASK,
    XBUS_TAMPER_INPUT_MASK,
    XBUS_TAMPER_ISOLATE_MASK,
    ZONE_DISCOVERY_MAX_ID,
    ZONE_POLL_BATCH_SIZE,
    ZONE_POLL_INTERVAL,
    ZONE_POLL_PHASE,
)
from .flexc.connection import FlexCClient, FlexCError
from .flexc.discovery import (
    async_discover_areas,
    async_discover_doors,
    async_discover_zones,
)
from .flexc.events import (
    apply_area_event,
    apply_area_intrusion_event,
    apply_event,
    apply_panel_event,
    apply_xbus_event,
    apply_zone_event,
)
from .flexc.flexml import FlexMLError
from .flexc.read_retry import async_retry_read_once
from .flexc.xbus import async_get_xbus_status
from .models import (
    AreaState,
    AtpState,
    AtsState,
    DoorState,
    PanelState,
    SpcState,
    XBusDeviceState,
    ZoneState,
)
from .user_names import display_user_name

_LOGGER = logging.getLogger(__name__)


def poll_delay_for_phase(phase: float, interval: float) -> float:
    """Return the delay to the next fixed phase on the monotonic loop clock."""
    now = asyncio.get_running_loop().time()
    position = now % interval
    delay = (phase - position) % interval
    if delay < 0.001:
        return interval
    return delay


def _float_value(value: Any, suffix: str = "") -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if suffix and text.endswith(suffix):
        text = text[: -len(suffix)].strip()
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _int_value(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _bool_value(value: Any) -> bool | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "0":
        return False
    if text == "1":
        return True
    return None


def _spc_datetime(value: Any, timezone: tzinfo) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.strptime(str(value).strip(), "%H%M%S%d%m%Y").replace(
            tzinfo=timezone
        )
    except ValueError:
        return None


def _panel_state_from_summary(summary: dict[str, str]) -> PanelState:
    return PanelState(
        battery_voltage=_float_value(summary.get("SPC_BATT_VOLT"), "V"),
        aux_voltage=_float_value(summary.get("SPC_AUX_VOLT"), "V"),
        aux_current=_float_value(summary.get("SPC_AUX_CURR"), "mA"),
        ac_frequency=_float_value(summary.get("SPC_AC_FREQ"), "Hz"),
        rf_type=_int_value(summary.get("SPC_RF_TYPE")),
        rf_version=summary.get("SPC_RF_VERSION"),
        internal_bells=_bool_value(summary.get("INTERNAL_BELLS")),
        external_bells=_bool_value(summary.get("EXTERNAL_BELLS")),
        engineer_mode=_bool_value(summary.get("ENG_MODE")),
        installation_name=summary.get("INSTALLATION_NAME"),
        spc_type=summary.get("SPC_TYPE"),
        spc_variant=summary.get("SPC_VARIANT"),
        serial_number=summary.get("SPC_SERIAL_NO"),
        firmware_version=summary.get("SPC_FW_VERSION"),
        hardware_version=summary.get("SPC_HW_VERSION"),
        raw=dict(summary),
        updated_at=datetime.now(UTC),
    )


def _ats_state_from_status(response: dict[str, Any], timezone: tzinfo) -> AtsState:
    raw_ats = response["ats"]
    ats = AtsState(
        ats_id=int(raw_ats["ATS_ID"]),
        name=raw_ats.get("ATS_NAME"),
        registration_id=raw_ats.get("REGISTRATION_ID"),
        status=_int_value(raw_ats.get("ATS_STATUS")),
        state=_int_value(raw_ats.get("ATS_STATE")),
        event_log_count=_int_value(raw_ats.get("EVENT_LOG_COUNT")),
        updated_at=datetime.now(UTC),
    )
    for raw_atp in response["atps"]:
        atp_id = int(raw_atp["ATP_ID"])
        ats.atps[atp_id] = AtpState(
            atp_id=atp_id,
            name=raw_atp.get("ATP_NAME"),
            uid=_int_value(raw_atp.get("ATP_UID")),
            status=_int_value(raw_atp.get("ATP_STATUS")),
            state=_int_value(raw_atp.get("ATP_STATE")),
            connect_state=_int_value(raw_atp.get("ATP_CONNECT_STATE")),
            last_tx_ok_timestamp=_spc_datetime(
                raw_atp.get("LAST_TX_OK_TIMESTAMP"), timezone
            ),
        )
    return ats


def _area_reconciliation_changes(
    previous: dict[str, str], current: dict[str, str]
) -> list[str]:
    """Describe only changed area status fields without dumping the full payload."""
    return [
        f"{key}={previous.get(key)!r} -> {current.get(key)!r}"
        for key in sorted(previous.keys() | current.keys())
        if previous.get(key) != current.get(key)
    ]


def _area_state_from_status(raw_area: dict[str, str], timezone: tzinfo) -> AreaState:
    return AreaState(
        area_id=int(raw_area["AREA_ID"]),
        name=raw_area.get("AREA_NAME"),
        mode=_int_value(raw_area.get("MODE")),
        partset_a_enabled=_bool_value(raw_area.get("PARTSETA_ENABLE")),
        partset_b_enabled=_bool_value(raw_area.get("PARTSETB_ENABLE")),
        last_set_time=_spc_datetime(raw_area.get("LAST_SET_TIME"), timezone),
        last_set_user_id=_int_value(raw_area.get("LAST_SET_USER_ID")),
        last_set_user_name=raw_area.get("LAST_SET_USER_NAME"),
        last_unset_time=_spc_datetime(raw_area.get("LAST_UNSET_TIME"), timezone),
        last_unset_user_id=_int_value(raw_area.get("LAST_UNSET_USER_ID")),
        last_unset_user_name=raw_area.get("LAST_UNSET_USER_NAME"),
        last_alarm=_spc_datetime(raw_area.get("LAST_ALARM"), timezone),
        internal_bells=_bool_value(raw_area.get("INTERNAL_BELLS")),
        external_bells=_bool_value(raw_area.get("EXTERNAL_BELLS")),
        raw=dict(raw_area),
        updated_at=datetime.now(UTC),
    )


def _zone_state_from_status(raw_zone: dict[str, str]) -> ZoneState:
    return ZoneState(
        zone_id=int(raw_zone["ZONE_ID"]),
        name=raw_zone.get("ZONE_NAME"),
        area_id=_int_value(raw_zone.get("AREA_ID")),
        area_name=raw_zone.get("AREA_NAME"),
        zone_type=_int_value(raw_zone.get("TYPE")),
        input_state=_int_value(raw_zone.get("INPUT")),
        logic_input=_int_value(raw_zone.get("LOGIC_INPUT")),
        status=_int_value(raw_zone.get("STATUS")),
        proc_state=_int_value(raw_zone.get("PROC_STATE")),
        alarm_state=_int_value(raw_zone.get("ALARM_STATE")),
        inhibit_allowed=_bool_value(raw_zone.get("INHIBIT_ALLOWED")),
        isolate_allowed=_bool_value(raw_zone.get("ISOLATE_ALLOWED")),
        restore_allowed=_bool_value(raw_zone.get("RESTORE_ALLOWED")),
        actuations_since_last_read=_int_value(
            raw_zone.get("ACTUATIONS_SINCE_LAST_READ")
        ),
        raw=dict(raw_zone),
        updated_at=datetime.now(UTC),
    )


def _reconcile_zone_event_state(zone: ZoneState, previous: ZoneState | None) -> bool:
    """Preserve event history, but clear stale tamper on confirmed normal status.

    Only a complete, explicitly normal status can override a missed restore
    EVENT. Missing fields are not evidence of recovery.
    """
    if previous is None:
        return False

    zone.last_event = previous.last_event
    zone.event_tamper = previous.event_tamper
    if (
        zone.event_tamper is True
        and all(
            value == 0
            for value in (
                zone.logic_input,
                zone.status,
                zone.proc_state,
                zone.alarm_state,
            )
        )
        and all(
            value is not None
            for value in (
                zone.logic_input,
                zone.status,
                zone.proc_state,
                zone.alarm_state,
            )
        )
    ):
        zone.event_tamper = False

    return zone.event_tamper != previous.event_tamper


def _door_state_from_status(raw_door: dict[str, str]) -> DoorState:
    return DoorState(
        door_id=int(raw_door["DOOR_ID"]),
        name=raw_door.get("DOOR_NAME") or raw_door.get("NAME"),
        mode=_int_value(raw_door.get("DOOR_MODE") or raw_door.get("MODE")),
        raw=dict(raw_door),
        updated_at=datetime.now(UTC),
    )


def _xbus_mask_state(raw_value: str | None, mask: int) -> bool | None:
    """Return a validated X-BUS bit state from a hexadecimal status field."""
    if raw_value is None:
        return None
    try:
        return bool(int(raw_value, 16) & mask)
    except ValueError:
        return None


def _xbus_device_state_from_status(
    raw_device: dict[str, str],
    previous: XBusDeviceState | None = None,
) -> XBusDeviceState | None:
    """Build an X-BUS device and reconcile tamper state from status."""
    device_id = _int_value(raw_device.get("ID"))
    if device_id is None:
        _LOGGER.warning("Ignoring X-BUS ENETNODE without a valid ID: %s", raw_device)
        return None

    return XBusDeviceState(
        device_id=device_id,
        name=raw_device.get("NAME"),
        serial_number=raw_device.get("SN"),
        device_type=_int_value(raw_device.get("TYPE")),
        hardware_id=_int_value(raw_device.get("HARDWARE_ID")),
        input_count=_int_value(raw_device.get("ICOUNT")),
        output_count=_int_value(raw_device.get("OCOUNT")),
        version=raw_device.get("VERSION"),
        rf_type=_int_value(raw_device.get("RF_TYPE")),
        rf_version=raw_device.get("RF_VERSION"),
        reader_type=_int_value(raw_device.get("READER_TYPE")),
        status_raw=raw_device.get("STATUS"),
        position_1=_int_value(raw_device.get("POSITION_1")),
        position_2=_int_value(raw_device.get("POSITION_2")),
        psu_type=_int_value(raw_device.get("PSU_TYPE")),
        aux_voltage=_float_value(raw_device.get("AUX_VOLT"), "V"),
        aux_current=_float_value(raw_device.get("AUX_CURR"), "mA"),
        input_raw=raw_device.get("INPUT"),
        alert_raw=raw_device.get("ALERT"),
        inhibit_raw=raw_device.get("INHIBIT"),
        isolate_raw=raw_device.get("ISOLATE"),
        sia_address=previous.sia_address if previous is not None else None,
        tamper_fault=_xbus_mask_state(raw_device.get("INPUT"), XBUS_TAMPER_INPUT_MASK),
        tamper_inhibited=_xbus_mask_state(
            raw_device.get("INHIBIT"), XBUS_TAMPER_INHIBIT_MASK
        ),
        tamper_isolated=_xbus_mask_state(
            raw_device.get("ISOLATE"), XBUS_TAMPER_ISOLATE_MASK
        ),
        last_event=previous.last_event if previous is not None else None,
        raw=dict(raw_device),
        updated_at=datetime.now(UTC),
    )


class SpcFlexCCoordinator(DataUpdateCoordinator[SpcState]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_PANEL_INTERVAL),
        )
        self.entry = entry
        self.state = SpcState()
        self._tamper_store: Store[dict[str, bool]] = Store(
            hass, 1, f"{DOMAIN}.panel_tamper.{entry.entry_id}"
        )
        self._area_history_store: Store[dict[str, Any]] = Store(
            hass, 1, f"{DOMAIN}.area_history.{entry.entry_id}"
        )
        self._area_history: dict[int, dict[str, Any]] = {}
        self._user_names: dict[int, str] = {}
        self.client = FlexCClient(entry.data)
        self.client.set_event_callback(self._handle_flexc_event)
        self.client.set_session_ready_callback(self._handle_session_ready)
        self._detected_ats_ids: set[int] = set()
        self._ats_discovery_complete = False
        self._detected_area_ids: set[int] = set()
        self._area_discovery_complete = False
        self._detected_zone_ids: set[int] = set()
        self._zone_discovery_complete = False
        self._pending_zone_restores: set[tuple[int, int]] = set()
        self._detected_door_ids: set[int] = set()
        self._door_discovery_complete = False
        self._detected_xbus_serials: set[str] = set()
        self._xbus_discovery_complete = False
        self._discovery_requested = False
        self._client_operation_lock = asyncio.Lock()
        self._discovery_task: asyncio.Task[None] | None = None
        self._zone_poll_task: asyncio.Task[None] | None = None
        self._xbus_poll_task: asyncio.Task[None] | None = None
        self._reconnect_reconcile_task: asyncio.Task[None] | None = None
        self._pending_reconcile_generation = 0
        self._last_reconciled_generation = 0

    async def async_restore_panel_tamper(self) -> None:
        """Restore last event-confirmed panel tamper state, if available."""
        try:
            saved = await self._tamper_store.async_load()
        except Exception:  # Storage failure must not prevent alarm integration setup.
            _LOGGER.exception("Could not restore last known panel tamper state")
            return
        if isinstance(saved, dict) and type(saved.get("panel_tamper")) is bool:
            self.state.faults.panel_tamper = saved["panel_tamper"]
            _LOGGER.debug("Restored last known panel tamper state")

    async def async_restore_area_history(self) -> None:
        """Restore persisted area history, never stale operating modes."""
        try:
            saved = await self._area_history_store.async_load()
        except Exception:
            _LOGGER.exception("Could not restore SPC area history")
            return
        if not isinstance(saved, dict):
            return
        for raw_id, value in saved.items():
            area_id = _int_value(raw_id)
            if area_id is None or not isinstance(value, dict):
                continue
            history: dict[str, Any] = {}
            for kind in ("arm", "disarm"):
                raw_time = value.get(f"last_{kind}_time")
                if not isinstance(raw_time, str):
                    continue
                try:
                    timestamp = datetime.fromisoformat(raw_time)
                except ValueError:
                    continue
                if timestamp.tzinfo is None:
                    continue
                history[f"last_{kind}_time"] = timestamp
                history[f"last_{kind}_user_id"] = _int_value(
                    value.get(f"last_{kind}_user_id")
                )
                name = value.get(f"last_{kind}_user_name")
                history[f"last_{kind}_user_name"] = (
                    name if isinstance(name, str) else None
                )
                history[f"last_{kind}_user_display_name"] = history[
                    f"last_{kind}_user_name"
                ]
            if history:
                self._area_history[area_id] = history

    def _save_area_history(self) -> dict[str, Any]:
        """Persist timestamps and identities only, never raw event data."""
        saved: dict[str, Any] = {}
        for area_id, history in self._area_history.items():
            item: dict[str, Any] = {}
            for kind in ("arm", "disarm"):
                timestamp = history.get(f"last_{kind}_time")
                if not isinstance(timestamp, datetime):
                    continue
                item[f"last_{kind}_time"] = timestamp.isoformat()
                item[f"last_{kind}_user_id"] = history.get(f"last_{kind}_user_id")
                item[f"last_{kind}_user_name"] = history.get(f"last_{kind}_user_name")
            if item:
                saved[str(area_id)] = item
        return saved

    def _display_user_name(
        self, user_id: int | None, raw_name: str | None
    ) -> str | None:
        """Apply user aliases without changing the raw SPC identity."""
        return display_user_name(
            user_id,
            raw_name,
            self.entry.options.get(CONF_USER_ALIASES, {}),
            self._user_names,
        )

    def _merge_area_history(self, area: AreaState) -> None:
        """Retain event history when area polling rebuilds the state object."""
        history = self._area_history.get(area.area_id, {})
        for kind in ("arm", "disarm"):
            history[f"last_{kind}_user_display_name"] = self._display_user_name(
                history.get(f"last_{kind}_user_id"),
                history.get(f"last_{kind}_user_name"),
            )
            for suffix in ("time", "user_id", "user_name", "user_display_name"):
                field = f"last_{kind}_{suffix}"
                if field in history:
                    setattr(area, field, history[field])

    def _apply_area_history_event(self, event: dict[str, str]) -> bool:
        """Track arm/disarm events without accepting duplicates or stale events."""
        event_id = _int_value(event.get("EV_ID"))
        area_id = _int_value(event.get("AREA_ID"))
        if event_id not in (3501, 3502, 3503, 3504) or area_id is None:
            return False
        area = self.state.areas.get(area_id)
        if area is None:
            return False
        timestamp = _spc_datetime(
            event.get("TIMESTAMP"), dt_util.get_default_time_zone()
        )
        if timestamp is None:
            return False
        history = self._area_history.setdefault(area_id, {})
        timestamps = [
            history.get(field) for field in ("last_arm_time", "last_disarm_time")
        ]
        newest = max(
            (value for value in timestamps if isinstance(value, datetime)),
            default=None,
        )
        if newest is not None and timestamp <= newest:
            return False
        kind = "disarm" if event_id == 3501 else "arm"
        user_name = event.get("USER_NAME") or None
        history.update(
            {
                f"last_{kind}_time": timestamp,
                f"last_{kind}_user_id": _int_value(event.get("USER_ID")),
                f"last_{kind}_user_name": user_name,
                f"last_{kind}_user_display_name": self._display_user_name(
                    _int_value(event.get("USER_ID")), user_name
                ),
            }
        )
        self._merge_area_history(area)
        self._area_history_store.async_delay_save(self._save_area_history, 1)
        return True

    def _handle_session_ready(self, generation: int) -> None:
        """Schedule state reconciliation after a replacement FlexC session."""
        if not self._discovery_requested or not self._discovery_complete:
            return
        self._pending_reconcile_generation = max(
            self._pending_reconcile_generation, generation
        )
        if (
            self._reconnect_reconcile_task is not None
            and not self._reconnect_reconcile_task.done()
        ):
            return
        self._reconnect_reconcile_task = self.entry.async_create_background_task(
            self.hass,
            self._async_reconcile_after_reconnect(),
            name=f"{DOMAIN} reconnect reconciliation",
            eager_start=False,
        )

    async def _async_reconcile_after_reconnect(self) -> None:
        """Refresh known live state after the SPC establishes a new session."""
        try:
            while self._pending_reconcile_generation > self._last_reconciled_generation:
                generation = self._pending_reconcile_generation
                started = asyncio.get_running_loop().time()
                _LOGGER.info(
                    "FlexC state reconciliation started after connection #%d",
                    generation,
                )
                try:
                    async with self._client_operation_lock:
                        await self.client.async_ensure_connected()
                        changed = await self._async_reconcile_known_state_locked()
                except asyncio.CancelledError:
                    raise
                except (FlexCError, FlexMLError) as err:
                    _LOGGER.warning(
                        "FlexC state reconciliation for connection #%d was interrupted: %s",
                        generation,
                        err,
                    )
                    return

                if self._pending_reconcile_generation != generation:
                    _LOGGER.info(
                        "FlexC state reconciliation for connection #%d completed "
                        "after connection #%d became ready; a fresh reconciliation "
                        "will follow",
                        generation,
                        self._pending_reconcile_generation,
                    )
                self._last_reconciled_generation = generation
                if changed:
                    self.async_set_updated_data(self.state)
                elapsed = asyncio.get_running_loop().time() - started
                _LOGGER.info(
                    "FlexC state reconciliation completed after connection #%d "
                    "in %.3fs (changed=%s)",
                    generation,
                    elapsed,
                    changed,
                )
        finally:
            self._reconnect_reconcile_task = None
            if self._pending_reconcile_generation > self._last_reconciled_generation:
                self._handle_session_ready(self._pending_reconcile_generation)

    async def _async_reconcile_known_state_locked(self) -> bool:
        """Refresh known base states while the shared operation lock is held."""
        changed = False
        timezone = dt_util.get_default_time_zone()

        if self._area_discovery_complete and self._detected_area_ids:
            area_ids = sorted(self._detected_area_ids)
            raw_areas = await async_retry_read_once(
                lambda: self.client.async_get_area_status(area_ids),
                description="reconciling areas after reconnect",
            )
            for raw_area in raw_areas:
                area = _area_state_from_status(raw_area, timezone)
                previous_area = self.state.areas.get(area.area_id)
                if previous_area is None or previous_area.raw != area.raw:
                    if previous_area is None:
                        _LOGGER.info(
                            "Area %d discovered during reconnect", area.area_id
                        )
                    else:
                        changes = _area_reconciliation_changes(
                            previous_area.raw, area.raw
                        )
                        _LOGGER.info(
                            "Area %d reconciliation after reconnect: %s",
                            area.area_id,
                            ", ".join(changes),
                        )
                    changed = True
                self._reconcile_area_intrusion(area, previous_area)
                self._merge_area_history(area)
                self.state.areas[area.area_id] = area

        if self._zone_discovery_complete and self._detected_zone_ids:
            zone_ids = sorted(self._detected_zone_ids)
            for index in range(0, len(zone_ids), ZONE_POLL_BATCH_SIZE):
                batch = zone_ids[index : index + ZONE_POLL_BATCH_SIZE]
                raw_zones = await async_retry_read_once(
                    partial(self.client.async_get_zone_status, batch),
                    description=f"reconciling zones {batch[0]}..{batch[-1]} after reconnect",
                )
                for raw_zone in raw_zones:
                    zone = _zone_state_from_status(raw_zone)
                    previous_zone = self.state.zones.get(zone.zone_id)
                    event_changed = _reconcile_zone_event_state(zone, previous_zone)
                    if (
                        previous_zone is None
                        or previous_zone.raw != zone.raw
                        or event_changed
                    ):
                        changed = True
                    self.state.zones[zone.zone_id] = zone

        if self._xbus_discovery_complete:
            raw_devices = await async_retry_read_once(
                partial(async_get_xbus_status, self.client),
                description="reconciling X-BUS devices after reconnect",
            )
            seen_serials: set[str] = set()
            for raw_device in raw_devices:
                serial = raw_device.get("SN")
                if not serial:
                    continue
                previous_xbus = self.state.xbus_devices.get(serial)
                device = _xbus_device_state_from_status(raw_device, previous_xbus)
                if device is None:
                    continue
                seen_serials.add(serial)
                if previous_xbus is None or previous_xbus.raw != device.raw:
                    changed = True
                self.state.xbus_devices[serial] = device
            missing_serials = set(self.state.xbus_devices) - seen_serials
            for serial in missing_serials:
                del self.state.xbus_devices[serial]
                changed = True
            if seen_serials != self._detected_xbus_serials:
                self._detected_xbus_serials = seen_serials
                changed = True

        return changed

    async def _async_update_data(self) -> SpcState:
        try:
            async with self._client_operation_lock:
                await self.client.async_ensure_connected()
                summary = await async_retry_read_once(
                    self.client.async_get_panel_summary,
                    description="reading panel summary",
                )
                if summary:
                    self.state.panel = _panel_state_from_summary(summary)
                alerts = await async_retry_read_once(
                    self.client.async_get_alert_status,
                    description="reading panel alerts",
                )
                if not alerts:
                    self.state.faults.modem_1_fault = False
                    self.state.faults.modem_1_line_fault = False
                    self.state.faults.rf_jamming = False
                    self.state.faults.xbus_battery_fault = False
                    self.state.faults.xbus_mains_fault = False
                timezone = dt_util.get_default_time_zone()
                if self._ats_discovery_complete:
                    for ats_id in sorted(self._detected_ats_ids):
                        try:
                            ats_status = await async_retry_read_once(
                                partial(self.client.async_get_flexc_ats_status, ats_id),
                                description=f"reading ATS {ats_id}",
                            )
                        except FlexMLError as err:
                            _LOGGER.debug(
                                "Ignoring unavailable previously detected FlexC ATS %d: %s",
                                ats_id,
                                err,
                            )
                            continue
                        if ats_status:
                            ats = _ats_state_from_status(ats_status, timezone)
                            self.state.ats[ats.ats_id] = ats
                if self._area_discovery_complete and self._detected_area_ids:
                    area_ids = sorted(self._detected_area_ids)
                    raw_areas = await async_retry_read_once(
                        lambda: self.client.async_get_area_status(area_ids),
                        description="reading area status",
                    )
                    for raw_area in raw_areas:
                        area = _area_state_from_status(raw_area, timezone)
                        previous = self.state.areas.get(area.area_id)
                        if previous is not None and previous.mode != area.mode:
                            _LOGGER.warning(
                                "SPC area reconciliation changed mode: area_id=%d name=%r %s -> %s",
                                area.area_id,
                                area.name,
                                previous.mode,
                                area.mode,
                            )
                        self._reconcile_area_intrusion(area, previous)
                        self._merge_area_history(area)
                        self.state.areas[area.area_id] = area

            if self._discovery_requested and not self._discovery_complete:
                self._schedule_discovery()
            return self.state
        except FlexCError as err:
            raise UpdateFailed(f"FlexC update failed: {err}") from err

    @property
    def _discovery_complete(self) -> bool:
        return (
            self._ats_discovery_complete
            and self._area_discovery_complete
            and self._zone_discovery_complete
            and self._door_discovery_complete
            and self._xbus_discovery_complete
        )

    def async_start_background_discovery(self) -> None:
        self._discovery_requested = True
        self._schedule_discovery()

    def _schedule_discovery(self) -> None:
        if self._discovery_complete:
            return
        if self._discovery_task is not None and not self._discovery_task.done():
            return
        self._discovery_task = self.entry.async_create_background_task(
            self.hass,
            self._async_discover_panel_objects(),
            name=f"{DOMAIN} discovery",
            eager_start=False,
        )

    async def _async_discover_panel_objects(self) -> None:
        try:
            timezone = dt_util.get_default_time_zone()
            async with self._client_operation_lock:
                await self.client.async_ensure_connected()
                detected_ats_ids: set[int] = set()
                for ats_id in ATS_IDS:
                    try:
                        ats_status = await async_retry_read_once(
                            partial(self.client.async_get_flexc_ats_status, ats_id),
                            description=f"discovering ATS {ats_id}",
                        )
                    except FlexMLError as err:
                        _LOGGER.debug("FlexC ATS %d not detected: %s", ats_id, err)
                        continue
                    if ats_status:
                        ats = _ats_state_from_status(ats_status, timezone)
                        self.state.ats[ats.ats_id] = ats
                        detected_ats_ids.add(ats.ats_id)
                self._detected_ats_ids.update(detected_ats_ids)
                self._ats_discovery_complete = True
                detected_area_ids: set[int] = set()
                raw_areas = await async_retry_read_once(
                    lambda: async_discover_areas(self.client, AREA_DISCOVERY_MAX_ID),
                    description="discovering areas",
                )
                for raw_area in raw_areas:
                    area = _area_state_from_status(raw_area, timezone)
                    self._merge_area_history(area)
                    self.state.areas[area.area_id] = area
                    detected_area_ids.add(area.area_id)
                self._detected_area_ids.update(detected_area_ids)
                self._area_discovery_complete = True
                detected_zone_ids: set[int] = set()
                raw_zones = await async_retry_read_once(
                    lambda: async_discover_zones(self.client, ZONE_DISCOVERY_MAX_ID),
                    description="discovering zones",
                )
                for raw_zone in raw_zones:
                    zone = _zone_state_from_status(raw_zone)
                    self.state.zones[zone.zone_id] = zone
                    detected_zone_ids.add(zone.zone_id)
                self._detected_zone_ids.update(detected_zone_ids)
                self._zone_discovery_complete = True
                detected_door_ids: set[int] = set()
                raw_doors = await async_retry_read_once(
                    lambda: async_discover_doors(self.client, DOOR_DISCOVERY_MAX_ID),
                    description="discovering doors",
                )
                for raw_door in raw_doors:
                    door = _door_state_from_status(raw_door)
                    self.state.doors[door.door_id] = door
                    detected_door_ids.add(door.door_id)
                self._detected_door_ids.update(detected_door_ids)
                self._door_discovery_complete = True
                detected_xbus_serials: set[str] = set()
                raw_xbus_devices = await async_retry_read_once(
                    partial(async_get_xbus_status, self.client),
                    description="discovering X-BUS devices",
                )
                for raw_device in raw_xbus_devices:
                    serial = raw_device.get("SN")
                    if not serial:
                        _LOGGER.warning(
                            "Ignoring X-BUS ENETNODE without a serial number: %s",
                            raw_device,
                        )
                        continue
                    previous = self.state.xbus_devices.get(serial)
                    device = _xbus_device_state_from_status(raw_device, previous)
                    if device is None:
                        continue
                    self.state.xbus_devices[serial] = device
                    detected_xbus_serials.add(serial)
                self._detected_xbus_serials = detected_xbus_serials
                self._xbus_discovery_complete = True
                # Resolve only users referenced by restored events; do not scan
                # the whole user database or persist sensitive user configuration.
                known_user_ids = {
                    user_id
                    for history in self._area_history.values()
                    for kind in ("arm", "disarm")
                    if isinstance((user_id := history.get(f"last_{kind}_user_id")), int)
                    and 1 <= user_id <= 9999
                }
                for user_id in sorted(known_user_ids):
                    try:
                        name = await self.client.async_get_user_name(user_id)
                    except (FlexCError, FlexMLError, ValueError):
                        # Responses may contain private fields: never log them.
                        continue
                    if name:
                        self._user_names[user_id] = name
                for area in self.state.areas.values():
                    self._merge_area_history(area)
            _LOGGER.info(
                "FlexC discovery completed: ATS=%s areas=%s zones=%s doors=%s X-BUS=%s",
                sorted(self._detected_ats_ids),
                sorted(self._detected_area_ids),
                sorted(self._detected_zone_ids),
                sorted(self._detected_door_ids),
                sorted(self._detected_xbus_serials),
            )
            self.async_set_updated_data(self.state)
            self._schedule_zone_polling()
            self._schedule_xbus_polling()
        except asyncio.CancelledError:
            raise
        except (FlexCError, FlexMLError) as err:
            _LOGGER.debug("FlexC background discovery interrupted: %s", err)
        finally:
            current_task = asyncio.current_task()
            if self._discovery_task is current_task:
                self._discovery_task = None

    def _should_run_polling(self) -> bool:
        """Allow polling only while discovery is active and HA is running."""
        return self._discovery_requested and self.hass.state not in (
            CoreState.stopping,
            CoreState.stopped,
        )

    def _schedule_zone_polling(self) -> None:
        if not self._should_run_polling():
            return
        if not self._zone_discovery_complete or not self._detected_zone_ids:
            return
        if self._zone_poll_task is not None and not self._zone_poll_task.done():
            return
        self._zone_poll_task = self.entry.async_create_background_task(
            self.hass,
            self._async_zone_poll_loop(),
            name=f"{DOMAIN} zone polling",
            eager_start=False,
        )

    async def _async_zone_poll_loop(self) -> None:
        """Poll zones without allowing one malformed reply to stop live updates."""
        _LOGGER.debug("SPC zone polling started")
        try:
            while True:
                await asyncio.sleep(
                    poll_delay_for_phase(ZONE_POLL_PHASE, ZONE_POLL_INTERVAL)
                )
                if not self._zone_discovery_complete:
                    continue
                zone_ids = sorted(self._detected_zone_ids)
                if not zone_ids:
                    continue
                try:
                    raw_zones: list[dict[str, str]] = []
                    async with self._client_operation_lock:
                        await self.client.async_ensure_connected()
                        for index in range(0, len(zone_ids), ZONE_POLL_BATCH_SIZE):
                            batch = zone_ids[index : index + ZONE_POLL_BATCH_SIZE]
                            batch_zones = await async_retry_read_once(
                                partial(self.client.async_get_zone_status, batch),
                                description=f"polling zones {batch[0]}..{batch[-1]}",
                            )
                            raw_zones.extend(batch_zones)

                    changed = False
                    restored_area_ids: set[int] = set()
                    for raw_zone in raw_zones:
                        zone = _zone_state_from_status(raw_zone)
                        previous = self.state.zones.get(zone.zone_id)
                        event_changed = _reconcile_zone_event_state(zone, previous)
                        # Diagnostic only: track SPC zone status while an area
                        # retains an intrusion. Do not infer alarm clearance here.
                        area = (
                            self.state.areas.get(zone.area_id)
                            if zone.area_id is not None
                            else None
                        )
                        if (
                            _LOGGER.isEnabledFor(logging.DEBUG)
                            and area is not None
                            and area.alarm_event_active
                        ):
                            before_status = (
                                (
                                    previous.alarm_state,
                                    previous.proc_state,
                                    previous.restore_allowed,
                                )
                                if previous is not None
                                else None
                            )
                            after_status = (
                                zone.alarm_state,
                                zone.proc_state,
                                zone.restore_allowed,
                            )
                            if before_status != after_status:
                                _LOGGER.debug(
                                    "FlexC zone restore diagnostic: "
                                    "AREA_ID=%s ZONE_ID=%s "
                                    "before=%s after=%s",
                                    zone.area_id,
                                    zone.zone_id,
                                    before_status,
                                    after_status,
                                )
                        if (
                            event_changed
                            or previous is None
                            or (
                                previous.input_state != zone.input_state
                                or previous.logic_input != zone.logic_input
                                or previous.proc_state != zone.proc_state
                                or previous.status != zone.status
                                or previous.alarm_state != zone.alarm_state
                                or previous.inhibited != zone.inhibited
                                or previous.restore_allowed != zone.restore_allowed
                                or previous.actuations_since_last_read
                                != zone.actuations_since_last_read
                            )
                        ):
                            changed = True
                        # A restore event may arrive after polling already
                        # observed ALARM_STATE=0. Keep its pending confirmation
                        # until the next authoritative zone-status response.
                        if (
                            zone.area_id is not None
                            and (zone.area_id, zone.zone_id)
                            in self._pending_zone_restores
                        ):
                            restored_area_ids.add(zone.area_id)
                        self.state.zones[zone.zone_id] = zone
                    polled_zone_ids = {
                        _int_value(raw.get("ZONE_ID")) for raw in raw_zones
                    }
                    for area_id in restored_area_ids:
                        area = self.state.areas.get(area_id)
                        if (
                            area is None
                            or area.mode in (None, 0)
                            or not area.alarm_event_active
                        ):
                            continue
                        # Remove only individually confirmed restored zones;
                        # preserve the area alarm until the last one is cleared.
                        restored_zones = {
                            zone_id
                            for zone_id in area.triggered_alarm_zones
                            if (
                                (known_zone := self.state.zones.get(zone_id))
                                is not None
                                and known_zone.area_id == area_id
                                and known_zone.alarm_state == 0
                                and (area_id, zone_id) in self._pending_zone_restores
                                and zone_id in polled_zone_ids
                            )
                        }
                        if not restored_zones:
                            continue
                        area.triggered_alarm_zones.difference_update(restored_zones)
                        self._pending_zone_restores.difference_update(
                            {(area_id, zone_id) for zone_id in restored_zones}
                        )
                        # Active intrusion is cleared by FlexC return events, not
                        # by a restored alarm status alone.
                        _LOGGER.debug(
                            "FlexC confirmed zone alarm restoration: "
                            "AREA_ID=%s RESTORED=%s REMAINING=%s",
                            area_id,
                            tuple(sorted(restored_zones)),
                            tuple(sorted(area.triggered_alarm_zones)),
                        )
                        if (
                            not area.triggered_alarm_zones
                            and not area.active_alarm_zones
                        ):
                            area.alarm_event_active = False
                        changed = True
                    if changed:
                        self.async_set_updated_data(self.state)
                except asyncio.CancelledError:
                    raise
                except (FlexCError, FlexMLError) as err:
                    _LOGGER.debug("SPC zone polling failed: %s", err)
                except Exception:
                    _LOGGER.exception(
                        "Unexpected error while polling SPC zones; polling will continue"
                    )
        except asyncio.CancelledError:
            if self._should_run_polling():
                _LOGGER.warning(
                    "SPC zone polling cancelled: entry_state=%s hass_state=%s discovery_requested=%s",
                    self.entry.state,
                    self.hass.state,
                    self._discovery_requested,
                )
            else:
                _LOGGER.debug(
                    "SPC zone polling cancelled: entry_state=%s hass_state=%s discovery_requested=%s",
                    self.entry.state,
                    self.hass.state,
                    self._discovery_requested,
                )
            raise
        finally:
            _LOGGER.debug("SPC zone polling stopped")
            current_task = asyncio.current_task()
            if self._zone_poll_task is current_task:
                self._zone_poll_task = None
                if self._should_run_polling():
                    _LOGGER.warning("SPC zone polling stopped unexpectedly; restarting")
                    self._schedule_zone_polling()

    def _schedule_xbus_polling(self) -> None:
        """Start periodic aggregate X-BUS reconciliation."""
        if not self._should_run_polling():
            return
        if not self._xbus_discovery_complete:
            return
        if self._xbus_poll_task is not None and not self._xbus_poll_task.done():
            return
        self._xbus_poll_task = self.entry.async_create_background_task(
            self.hass,
            self._async_xbus_poll_loop(),
            name=f"{DOMAIN} X-BUS polling",
            eager_start=False,
        )

    async def _async_xbus_poll_loop(self) -> None:
        """Periodically reconcile X-BUS inventory and raw status fields."""
        _LOGGER.debug("SPC X-BUS polling started")
        try:
            while True:
                await asyncio.sleep(
                    poll_delay_for_phase(XBUS_POLL_PHASE, XBUS_POLL_INTERVAL)
                )
                if not self._xbus_discovery_complete:
                    continue
                try:
                    async with self._client_operation_lock:
                        await self.client.async_ensure_connected()
                        raw_devices = await async_retry_read_once(
                            partial(async_get_xbus_status, self.client),
                            description="polling X-BUS devices",
                        )

                    changed = False
                    seen_serials: set[str] = set()
                    for raw_device in raw_devices:
                        serial = raw_device.get("SN")
                        if not serial:
                            _LOGGER.warning(
                                "Ignoring X-BUS ENETNODE without a serial number: %s",
                                raw_device,
                            )
                            continue
                        previous = self.state.xbus_devices.get(serial)
                        device = _xbus_device_state_from_status(raw_device, previous)
                        if device is None:
                            continue
                        seen_serials.add(serial)
                        if previous is None or previous.raw != device.raw:
                            changed = True
                        self.state.xbus_devices[serial] = device

                    missing_serials = set(self.state.xbus_devices) - seen_serials
                    if missing_serials:
                        changed = True
                        for serial in missing_serials:
                            del self.state.xbus_devices[serial]

                    if seen_serials != self._detected_xbus_serials:
                        self._detected_xbus_serials = seen_serials
                        changed = True

                    if changed:
                        self.async_set_updated_data(self.state)
                except asyncio.CancelledError:
                    raise
                except (FlexCError, FlexMLError) as err:
                    _LOGGER.debug("SPC X-BUS polling failed: %s", err)
                except Exception:
                    _LOGGER.exception(
                        "Unexpected error while polling SPC X-BUS; polling will continue"
                    )
        except asyncio.CancelledError:
            if self._should_run_polling():
                _LOGGER.warning(
                    "SPC X-BUS polling cancelled: entry_state=%s hass_state=%s discovery_requested=%s",
                    self.entry.state,
                    self.hass.state,
                    self._discovery_requested,
                )
            else:
                _LOGGER.debug(
                    "SPC X-BUS polling cancelled: entry_state=%s hass_state=%s discovery_requested=%s",
                    self.entry.state,
                    self.hass.state,
                    self._discovery_requested,
                )
            raise
        finally:
            _LOGGER.debug("SPC X-BUS polling stopped")
            current_task = asyncio.current_task()
            if self._xbus_poll_task is current_task:
                self._xbus_poll_task = None
                if self._should_run_polling():
                    _LOGGER.warning(
                        "SPC X-BUS polling stopped unexpectedly; restarting"
                    )
                    self._schedule_xbus_polling()

    async def async_shutdown(self) -> None:
        self._discovery_requested = False
        zone_task = self._zone_poll_task
        self._zone_poll_task = None
        if zone_task is not None and not zone_task.done():
            zone_task.cancel()
            with suppress(asyncio.CancelledError):
                await zone_task
        xbus_task = self._xbus_poll_task
        self._xbus_poll_task = None
        if xbus_task is not None and not xbus_task.done():
            xbus_task.cancel()
            with suppress(asyncio.CancelledError):
                await xbus_task
        reconcile_task = self._reconnect_reconcile_task
        self._reconnect_reconcile_task = None
        if reconcile_task is not None and not reconcile_task.done():
            reconcile_task.cancel()
            with suppress(asyncio.CancelledError):
                await reconcile_task
        discovery_task = self._discovery_task
        self._discovery_task = None
        if discovery_task is not None and not discovery_task.done():
            discovery_task.cancel()
            with suppress(asyncio.CancelledError):
                await discovery_task
        await self.client.async_close()

    @staticmethod
    def _reconcile_area_intrusion(area: AreaState, previous: AreaState | None) -> None:
        """Preserve alarm events across polling; clear them on confirmed unset."""
        if area.mode == 0:
            return
        if previous is not None and previous.mode == area.mode:
            area.active_alarm_zones = set(previous.active_alarm_zones)
            area.triggered_alarm_zones = set(previous.triggered_alarm_zones)
            area.alarm_event_active = previous.alarm_event_active

    def _handle_flexc_event(self, event: dict[str, str]) -> None:
        # Diagnostic only: do not log raw EVENT attributes (may contain user data).
        def _number(key: str) -> int | None:
            try:
                return int(str(event.get(key)))
            except (TypeError, ValueError):
                return None

        event_id = _number("EV_ID")
        area_id = _number("AREA_ID")
        zone_id = _number("ZONE_ID")
        diagnostic_area = self.state.areas.get(area_id) if area_id is not None else None

        def _alarm_snapshot() -> (
            tuple[int | None, bool, tuple[int, ...], tuple[int, ...]] | None
        ):
            if diagnostic_area is None:
                return None
            return (
                diagnostic_area.mode,
                diagnostic_area.alarm_event_active,
                tuple(sorted(diagnostic_area.active_alarm_zones)),
                tuple(sorted(diagnostic_area.triggered_alarm_zones)),
            )

        before = _alarm_snapshot() if _LOGGER.isEnabledFor(logging.DEBUG) else None
        fault_changed = apply_event(self.state.faults, event)
        if fault_changed and str(event.get("EV_ID")) in ("5206", "5207"):
            panel_tamper = self.state.faults.panel_tamper
            if panel_tamper is not None:
                self._tamper_store.async_delay_save(
                    lambda: {"panel_tamper": panel_tamper}, 1
                )
        panel_changed = apply_panel_event(self.state.panel, event)
        history_changed = SpcFlexCCoordinator._apply_area_history_event(self, event)
        # Ignore duplicate/out-of-order mode events; preserve the current mode.
        is_mode_event = event_id in (3501, 3502, 3503, 3504)
        # Events without timestamps still carry valid live state transitions.
        # Only reject a mode event when its timestamp is provably stale.
        event_time = (
            _spc_datetime(event.get("TIMESTAMP"), dt_util.get_default_time_zone())
            if is_mode_event
            else None
        )
        area_history = (
            self._area_history.get(area_id, {}) if area_id is not None else {}
        )
        latest_time = max(
            (
                value
                for key in ("last_arm_time", "last_disarm_time")
                if isinstance((value := area_history.get(key)), datetime)
            ),
            default=None,
        )
        stale_mode_event = (
            is_mode_event
            and event_time is not None
            and latest_time is not None
            and event_time < latest_time
        )
        area_changed = (
            False if stale_mode_event else apply_area_event(self.state.areas, event)
        )
        intrusion_changed = apply_area_intrusion_event(self.state.areas, event)
        if event_id in (1100, 1101) and area_id is not None and zone_id is not None:
            area = self.state.areas.get(area_id)
            if (
                area is not None
                and area.mode in (1, 2, 3)
                and zone_id in area.triggered_alarm_zones
            ):
                self._pending_zone_restores.add((area_id, zone_id))
                if zone_id in area.active_alarm_zones:
                    area.active_alarm_zones.discard(zone_id)
                    intrusion_changed = True
        elif event_id in (1000, 1001) and area_id is not None and zone_id is not None:
            self._pending_zone_restores.discard((area_id, zone_id))
        elif event_id == 3501 and area_id is not None:
            self._pending_zone_restores = {
                key for key in self._pending_zone_restores if key[0] != area_id
            }
        if str(event.get("EV_ID")) == "3501":
            try:
                area_id = int(str(event.get("AREA_ID")))
            except (TypeError, ValueError):
                area_id = None
            area = self.state.areas.get(area_id) if area_id is not None else None
            if area is not None and area.mode == 0:
                if (
                    area.alarm_event_active
                    or area.active_alarm_zones
                    or area.triggered_alarm_zones
                ):
                    intrusion_changed = True
                area.active_alarm_zones.clear()
                area.triggered_alarm_zones.clear()
                area.alarm_event_active = False
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "FlexC alarm diagnostic: EV_ID=%s AREA_ID=%s ZONE_ID=%s "
                "before=%s after=%s",
                event_id,
                area_id,
                zone_id,
                before,
                _alarm_snapshot(),
            )
        zone_changed = apply_zone_event(self.state.zones, event)
        xbus_changed = apply_xbus_event(self.state.xbus_devices, event)
        if (
            fault_changed
            or panel_changed
            or area_changed
            or history_changed
            or intrusion_changed
            or zone_changed
            or xbus_changed
        ):
            self.async_set_updated_data(self.state)
