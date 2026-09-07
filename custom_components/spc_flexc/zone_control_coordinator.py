"""Zone-control coordinator extensions for SPC FlexC."""

from __future__ import annotations

from .coordinator import SpcFlexCCoordinator
from .flexc.zone_control import async_set_zone_inhibited


class SpcFlexCZoneControlCoordinator(SpcFlexCCoordinator):
    """SPC coordinator with validated zone inhibition controls."""

    async def async_set_zone_inhibited(self, zone_id: int, inhibited: bool) -> None:
        """Set zone inhibition and refresh the zone state immediately."""
        zone = self.state.zones.get(zone_id)
        if zone is None:
            raise ValueError(f"Unknown SPC zone {zone_id}")

        if inhibited:
            if zone.inhibited is True:
                return
            if zone.inhibit_allowed is not True:
                raise ValueError(f"SPC zone {zone_id} does not currently allow inhibition")
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
            raw_zones = await self.client.async_get_zone_status([zone_id])

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
