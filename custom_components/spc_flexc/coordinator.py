import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DEFAULT_PANEL_INTERVAL, DOMAIN
from .flexc.connection import FlexCClient, FlexCError
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

    async def _async_update_data(self) -> SpcState:
        """Update SPC data."""
        try:
            await self.client.async_ensure_connected()

            summary = await self.client.async_get_panel_summary()

            if summary:
                self.state.panel = _panel_state_from_summary(summary)

            ats_status = await self.client.async_get_flexc_ats_status(1)

            if ats_status:
                ats = _ats_state_from_status(
                    ats_status,
                    ZoneInfo(self.hass.config.time_zone),
                )
                self.state.ats[ats.ats_id] = ats

            return self.state

        except FlexCError as err:
            # IMPORTANT:
            # Do not clear self.state.ats here.
            #
            # It intentionally remains the last known ATS/ATP state.
            raise UpdateFailed(f"FlexC update failed: {err}") from err

    async def async_shutdown(self) -> None:
        """Close the FlexC connection."""
        await self.client.async_close()
