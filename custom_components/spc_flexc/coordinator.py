import asyncio
import logging
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    AREA_IDS,
    ATS_IDS,
    DEFAULT_PANEL_INTERVAL,
    DOMAIN,
    ZONE_IDS,
)
from .flexc.connection import FlexCClient, FlexCError
from .flexc.events import (
    apply_event,
    apply_panel_event,
    apply_xbus_event,
    apply_zone_event,
)
from .flexc.flexml import FlexMLError
from .models import (
    AreaState,
    AtpState,
    AtsState,
    PanelState,
    SpcState,
    ZoneState,
)

_LOGGER = logging.getLogger(__name__)

ZONE_POLL_INTERVAL = 1.0


def _float_value(value: Any, suffix: str = "") -> float | None:
    """Convert an SPC numeric string with an optional unit suffix."""
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
    """Convert an SPC value to int."""
    if value is None:
        return None

    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _bool_value(value: Any) -> bool | None:
    """Convert an SPC 0/1 value to bool."""
    if value is None:
        return None

    text = str(value).strip()

    if text == "0":
        return False

    if text == "1":
        return True

    return None


def _spc_datetime(
    value: Any,
    timezone: ZoneInfo,
) -> datetime | None:
    """Convert an SPC HHMMSSDDMMYYYY timestamp."""
    if value is None:
        return None

    text = str(value).strip()

    try:
        return datetime.strptime(
            text,
            "%H%M%S%d%m%Y",
        ).replace(tzinfo=timezone)
    except ValueError:
        return None


def _panel_state_from_summary(
    summary: dict[str, str],
) -> PanelState:
    """Convert raw PANEL_SUMMARY attributes to PanelState."""
    return PanelState(
        battery_voltage=_float_value(
            summary.get("SPC_BATT_VOLT"),
            "V",
        ),
        aux_voltage=_float_value(
            summary.get("SPC_AUX_VOLT"),
            "V",
        ),
        aux_current=_float_value(
            summary.get("SPC_AUX_CURR"),
            "mA",
        ),
        ac_frequency=_float_value(
            summary.get("SPC_AC_FREQ"),
            "Hz",
        ),
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


def _ats_state_from_status(
    response: dict[str, Any],
    timezone: ZoneInfo,
) -> AtsState:
    """Convert raw FlexC ATS status to persistent state."""
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
                raw_atp.get("LAST_TX_OK_TIMESTAMP"),
                timezone,
            ),
        )

    return ats


def _area_state_from_status(
    raw_area: dict[str, str],
    timezone: ZoneInfo,
) -> AreaState:
    """Convert raw AREA_STATUS attributes to AreaState."""
    return AreaState(
        area_id=int(raw_area["AREA_ID"]),
        name=raw_area.get("AREA_NAME"),
        mode=_int_value(raw_area.get("MODE")),
        partset_a_enabled=_bool_value(raw_area.get("PARTSETA_ENABLE")),
        partset_b_enabled=_bool_value(raw_area.get("PARTSETB_ENABLE")),
        last_set_time=_spc_datetime(
            raw_area.get("LAST_SET_TIME"),
            timezone,
        ),
        last_set_user_id=_int_value(raw_area.get("LAST_SET_USER_ID")),
        last_set_user_name=raw_area.get("LAST_SET_USER_NAME"),
        last_unset_time=_spc_datetime(
            raw_area.get("LAST_UNSET_TIME"),
            timezone,
        ),
        last_unset_user_id=_int_value(raw_area.get("LAST_UNSET_USER_ID")),
        last_unset_user_name=raw_area.get("LAST_UNSET_USER_NAME"),
        last_alarm=_spc_datetime(
            raw_area.get("LAST_ALARM"),
            timezone,
        ),
        internal_bells=_bool_value(raw_area.get("INTERNAL_BELLS")),
        external_bells=_bool_value(raw_area.get("EXTERNAL_BELLS")),
        raw=dict(raw_area),
        updated_at=datetime.now(UTC),
    )


def _zone_state_from_status(
    raw_zone: dict[str, str],
) -> ZoneState:
    """Convert raw ZONE_STATUS attributes to ZoneState."""
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
        actuations_since_last_read=_int_value(
            raw_zone.get("ACTUATIONS_SINCE_LAST_READ")
        ),
        raw=dict(raw_zone),
        updated_at=datetime.now(UTC),
    )


class SpcFlexCCoordinator(DataUpdateCoordinator[SpcState]):
    """Coordinate SPC FlexC updates."""

    def __init__(self, hass, entry):
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_PANEL_INTERVAL),
        )

        self.entry = entry
        self.state = SpcState()

        self.client = FlexCClient(entry.data)
        self.client.set_event_callback(self._handle_flexc_event)

        self._detected_ats_ids: set[int] = set()
        self._ats_discovery_complete = False

        self._detected_area_ids: set[int] = set()
        self._area_discovery_complete = False

        self._detected_zone_ids: set[int] = set()
        self._zone_discovery_complete = False

        self._ats_discovery_requested = False

        # Protect complete FlexC command sequences.
        #
        # FlexCClient already serializes individual FLEXML commands.
        # This lock additionally prevents PANEL_SUMMARY, ALERT_STATUS,
        # ATS/area polling, zone polling and background discovery
        # sequences from being interleaved.
        self._client_operation_lock = asyncio.Lock()

        self._ats_discovery_task: asyncio.Task[None] | None = None
        self._zone_poll_task: asyncio.Task[None] | None = None

    async def _async_update_data(self) -> SpcState:
        """Update slow-changing SPC data."""
        try:
            async with self._client_operation_lock:
                await self.client.async_ensure_connected()

                summary = await self.client.async_get_panel_summary()

                if summary:
                    self.state.panel = _panel_state_from_summary(summary)

                alerts = await self.client.async_get_alert_status()

                if not alerts:
                    self.state.faults.modem_1_fault = False
                    self.state.faults.modem_1_line_fault = False
                    self.state.faults.rf_jamming = False
                    self.state.faults.xbus_battery_fault = False
                    self.state.faults.xbus_mains_fault = False

                timezone = ZoneInfo(self.hass.config.time_zone)

                # Poll only ATS IDs discovered during startup.
                if self._ats_discovery_complete:
                    for ats_id in sorted(self._detected_ats_ids):
                        try:
                            ats_status = await self.client.async_get_flexc_ats_status(
                                ats_id
                            )
                        except FlexMLError as err:
                            _LOGGER.debug(
                                "Ignoring unavailable previously "
                                "detected FlexC ATS %d: %s",
                                ats_id,
                                err,
                            )
                            continue

                        if not ats_status:
                            continue

                        ats = _ats_state_from_status(
                            ats_status,
                            timezone,
                        )

                        self.state.ats[ats.ats_id] = ats

                # Poll only areas discovered during startup.
                if self._area_discovery_complete and self._detected_area_ids:
                    raw_areas = await self.client.async_get_area_status(
                        sorted(self._detected_area_ids)
                    )

                    for raw_area in raw_areas:
                        area = _area_state_from_status(
                            raw_area,
                            timezone,
                        )

                        self.state.areas[area.area_id] = area

            # Zones are deliberately NOT polled here.
            #
            # Their dedicated background loop has its own cadence
            # while sharing the same client operation lock.

            if self._ats_discovery_requested and (
                not self._ats_discovery_complete
                or not self._area_discovery_complete
                or not self._zone_discovery_complete
            ):
                self._schedule_ats_discovery()

            return self.state

        except FlexCError as err:
            # Preserve all last-known states when the FlexC transport
            # becomes unavailable.
            raise UpdateFailed(f"FlexC update failed: {err}") from err

    def async_start_background_discovery(self) -> None:
        """Enable and start background discovery."""
        self._ats_discovery_requested = True
        self._schedule_ats_discovery()

    def _schedule_ats_discovery(self) -> None:
        """Schedule discovery if it is not already running."""
        if (
            self._ats_discovery_complete
            and self._area_discovery_complete
            and self._zone_discovery_complete
        ):
            return

        task = self._ats_discovery_task

        if task is not None and not task.done():
            return

        self._ats_discovery_task = self.entry.async_create_background_task(
            self.hass,
            self._async_discover_ats(),
            name=f"{DOMAIN} discovery",
            eager_start=False,
        )

    async def _async_discover_ats(self) -> None:
        """Discover available ATS IDs, areas and zones."""
        try:
            detected_ats_ids: set[int] = set()
            detected_area_ids: set[int] = set()
            detected_zone_ids: set[int] = set()

            timezone = ZoneInfo(self.hass.config.time_zone)

            async with self._client_operation_lock:
                await self.client.async_ensure_connected()

                # Discover ATS.
                for ats_id in ATS_IDS:
                    try:
                        ats_status = await self.client.async_get_flexc_ats_status(
                            ats_id
                        )
                    except FlexMLError as err:
                        _LOGGER.debug(
                            "FlexC ATS %d not detected: %s",
                            ats_id,
                            err,
                        )
                        continue

                    if not ats_status:
                        continue

                    ats = _ats_state_from_status(
                        ats_status,
                        timezone,
                    )

                    self.state.ats[ats.ats_id] = ats
                    detected_ats_ids.add(ats.ats_id)

                self._detected_ats_ids.update(detected_ats_ids)
                self._ats_discovery_complete = True

                # Discover areas.
                raw_areas = await self.client.async_get_area_status(AREA_IDS)

                for raw_area in raw_areas:
                    area = _area_state_from_status(
                        raw_area,
                        timezone,
                    )

                    self.state.areas[area.area_id] = area
                    detected_area_ids.add(area.area_id)

                self._detected_area_ids.update(detected_area_ids)
                self._area_discovery_complete = True

                # Discover zones.
                raw_zones = await self.client.async_get_zone_status(ZONE_IDS)

                for raw_zone in raw_zones:
                    zone = _zone_state_from_status(raw_zone)

                    self.state.zones[zone.zone_id] = zone

                    detected_zone_ids.add(zone.zone_id)

                self._detected_zone_ids.update(detected_zone_ids)
                self._zone_discovery_complete = True

            _LOGGER.info(
                "FlexC ATS discovery completed: detected ATS IDs %s",
                sorted(self._detected_ats_ids),
            )

            _LOGGER.info(
                "SPC area discovery completed: detected area IDs %s",
                sorted(self._detected_area_ids),
            )

            _LOGGER.info(
                "SPC zone discovery completed: detected zone IDs %s",
                sorted(self._detected_zone_ids),
            )

            self.async_set_updated_data(self.state)

            # Start the dedicated zone polling only after
            # initial discovery and after releasing the operation lock.
            self._schedule_zone_polling()

        except asyncio.CancelledError:
            raise

        except (FlexCError, FlexMLError) as err:
            _LOGGER.debug(
                "FlexC background discovery interrupted: %s",
                err,
            )

        finally:
            current_task = asyncio.current_task()

            if self._ats_discovery_task is current_task:
                self._ats_discovery_task = None

    def _schedule_zone_polling(self) -> None:
        """Start dedicated zone polling if not already running."""
        if not self._zone_discovery_complete:
            return

        if not self._detected_zone_ids:
            return

        task = self._zone_poll_task

        if task is not None and not task.done():
            return

        self._zone_poll_task = self.entry.async_create_background_task(
            self.hass,
            self._async_zone_poll_loop(),
            name=f"{DOMAIN} zone polling",
            eager_start=False,
        )

    async def _async_zone_poll_loop(self) -> None:
        """Poll detected zones independently from the main refresh."""
        try:
            while True:
                await asyncio.sleep(ZONE_POLL_INTERVAL)

                if not self._zone_discovery_complete:
                    continue

                zone_ids = sorted(self._detected_zone_ids)

                if not zone_ids:
                    continue

                try:
                    async with self._client_operation_lock:
                        await self.client.async_ensure_connected()

                        raw_zones = await self.client.async_get_zone_status(zone_ids)

                except (
                    FlexCError,
                    FlexMLError,
                ) as err:
                    _LOGGER.debug(
                        "SPC zone polling failed: %s",
                        err,
                    )
                    continue

                changed = False

                for raw_zone in raw_zones:
                    zone = _zone_state_from_status(raw_zone)

                    previous = self.state.zones.get(zone.zone_id)

                    if previous is not None:
                        zone.event_tamper = previous.event_tamper
                        zone.last_event = previous.last_event

                    if previous is None or (
                        previous.input_state != zone.input_state
                        or previous.logic_input != zone.logic_input
                        or previous.proc_state != zone.proc_state
                        or previous.status != zone.status
                        or previous.alarm_state != zone.alarm_state
                    ):
                        changed = True

                    self.state.zones[zone.zone_id] = zone

                if changed:
                    self.async_set_updated_data(self.state)

        finally:
            current_task = asyncio.current_task()

            if self._zone_poll_task is current_task:
                self._zone_poll_task = None

    async def async_shutdown(self) -> None:
        """Stop background work and close the FlexC connection."""
        self._ats_discovery_requested = False

        zone_task = self._zone_poll_task
        self._zone_poll_task = None

        if zone_task is not None and not zone_task.done():
            zone_task.cancel()

            with suppress(asyncio.CancelledError):
                await zone_task

        discovery_task = self._ats_discovery_task
        self._ats_discovery_task = None

        if discovery_task is not None and not discovery_task.done():
            discovery_task.cancel()

            with suppress(asyncio.CancelledError):
                await discovery_task

        await self.client.async_close()

    def _handle_flexc_event(
        self,
        event: dict[str, str],
    ) -> None:
        """Apply one unsolicited FlexC EVENT 0x60."""

        fault_changed = apply_event(
            self.state.faults,
            event,
        )

        panel_changed = apply_panel_event(
            self.state.panel,
            event,
        )

        zone_changed = apply_zone_event(
            self.state.zones,
            event,
        )

        xbus_changed = apply_xbus_event(
            self.state.xbus_devices,
            event,
        )

        if fault_changed or panel_changed or zone_changed or xbus_changed:
            self.async_set_updated_data(self.state)
