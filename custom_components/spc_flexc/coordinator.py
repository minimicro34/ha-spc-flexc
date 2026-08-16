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

from .const import ATS_IDS, DEFAULT_PANEL_INTERVAL, DOMAIN
from .flexc.connection import FlexCClient, FlexCError
from .flexc.flexml import FlexMLError
from .models import AtpState, AtsState, PanelState, SpcState

_LOGGER = logging.getLogger(__name__)


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

        # ATS IDs successfully discovered during this coordinator lifetime.
        self._detected_ats_ids: set[int] = set()
        self._ats_discovery_complete = False

        # Becomes True only when async_start_ats_discovery() is called
        # after the config entry/platform setup has completed.
        self._ats_discovery_requested = False

        # Protect complete FlexC command sequences.
        #
        # FlexCClient already serializes individual FLEXML commands, but
        # this lock prevents PANEL_SUMMARY / ATS polling / ATS discovery
        # sequences from being interleaved with each other.
        self._client_operation_lock = asyncio.Lock()

        self._ats_discovery_task: asyncio.Task[None] | None = None

    async def _async_update_data(self) -> SpcState:
        """Update SPC data."""
        try:
            async with self._client_operation_lock:
                await self.client.async_ensure_connected()

                summary = await self.client.async_get_panel_summary()

                if summary:
                    self.state.panel = _panel_state_from_summary(summary)

                # ATS discovery is not performed during the first
                # config-entry refresh.
                #
                # Once discovery is complete, only ATS IDs that really
                # exist are polled during normal coordinator updates.
                if self._ats_discovery_complete:
                    timezone = ZoneInfo(self.hass.config.time_zone)

                    for ats_id in sorted(self._detected_ats_ids):
                        try:
                            ats_status = await self.client.async_get_flexc_ats_status(
                                ats_id
                            )
                        except FlexMLError as err:
                            # Keep the last known ATS/ATP state.
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

            # If the initial discovery previously failed because the
            # FlexC transport was unavailable, retry it after a later
            # successful normal refresh.
            if self._ats_discovery_requested and not self._ats_discovery_complete:
                self._schedule_ats_discovery()

            return self.state

        except FlexCError as err:
            # Preserve the last known PANEL / ATS / ATP state when
            # the FlexC connection itself is lost.
            raise UpdateFailed(f"FlexC update failed: {err}") from err

    def async_start_ats_discovery(self) -> None:
        """Enable and start ATS discovery in the background."""
        self._ats_discovery_requested = True
        self._schedule_ats_discovery()

    def _schedule_ats_discovery(self) -> None:
        """Schedule ATS discovery if it is not already running."""
        if self._ats_discovery_complete:
            return

        task = self._ats_discovery_task

        if task is not None and not task.done():
            return

        self._ats_discovery_task = self.entry.async_create_background_task(
            self.hass,
            self._async_discover_ats(),
            name=f"{DOMAIN} ATS discovery",
            eager_start=False,
        )

    async def _async_discover_ats(self) -> None:
        """Discover available FlexC ATS IDs in the background."""
        try:
            detected_ats_ids: set[int] = set()
            timezone = ZoneInfo(self.hass.config.time_zone)

            async with self._client_operation_lock:
                await self.client.async_ensure_connected()

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

            _LOGGER.info(
                "FlexC ATS discovery completed: detected ATS IDs %s",
                sorted(self._detected_ats_ids),
            )

            # Notify coordinator listeners immediately.
            #
            # sensor.py and binary_sensor.py will then create the
            # dynamically discovered ATS/ATP entities.
            self.async_set_updated_data(self.state)

        except asyncio.CancelledError:
            raise

        except FlexCError as err:
            # Keep discovery incomplete. It will be retried after a
            # later successful coordinator refresh.
            _LOGGER.debug(
                "FlexC ATS discovery interrupted: %s",
                err,
            )

        finally:
            current_task = asyncio.current_task()

            if self._ats_discovery_task is current_task:
                self._ats_discovery_task = None

    async def async_shutdown(self) -> None:
        """Stop background work and close the FlexC connection."""
        self._ats_discovery_requested = False

        task = self._ats_discovery_task
        self._ats_discovery_task = None

        if task is not None and not task.done():
            task.cancel()

            with suppress(asyncio.CancelledError):
                await task

        await self.client.async_close()
