"""FlexC EVENT 0x60 parsing and persistent fault mapping."""

from __future__ import annotations

import html
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from ..models import FaultState, XBusDeviceState

EVENT_STATE_MAP: dict[int, tuple[str, bool]] = {
    # Panel power.
    5000: ("mains_fault", True),
    5001: ("mains_fault", False),
    # Panel battery.
    5006: ("battery_fault", True),
    5007: ("battery_fault", False),
    # Panel enclosure tamper.
    5206: ("panel_tamper", True),
    5207: ("panel_tamper", False),
    # Modem 1.
    6100: ("modem_1_fault", True),
    6101: ("modem_1_fault", False),
    6106: ("modem_1_line_fault", True),
    6107: ("modem_1_line_fault", False),
    # X-BUS.
    5324: ("xbus_mains_fault", True),
    5325: ("xbus_mains_fault", False),
    5330: ("xbus_battery_fault", True),
    5331: ("xbus_battery_fault", False),
    # X-BUS radio jamming.
    5336: ("rf_jamming", True),
    5337: ("rf_jamming", False),
}

PANEL_EVENT_STATE_MAP: dict[int, tuple[str, bool]] = {
    7003: ("engineer_mode", True),
    7004: ("engineer_mode", False),
}

AREA_EVENT_MODE_MAP: dict[int, int] = {
    3501: 0,  # MHS / Unset
    3504: 3,  # MES Totale / Full Set
}


def parse_event_payload(
    payload: bytes,
) -> dict[str, str] | None:
    """Parse one EVENT XML object from a FlexC 0x60 payload."""
    raw = payload.split(b"\x00", 1)[0].strip()

    if not raw.startswith(b"<EVENT"):
        return None

    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return None

    if root.tag != "EVENT":
        return None

    return {key: html.unescape(value) for key, value in root.attrib.items()}


def apply_event(
    faults: FaultState,
    event: Mapping[str, Any],
) -> bool:
    """Apply a validated EVENT to persistent fault state.

    Return True when a known fault state changed.
    """
    raw_event_id = event.get("EV_ID")

    try:
        event_id = int(str(raw_event_id))
    except (TypeError, ValueError):
        faults.last_event = dict(event)
        return False

    faults.last_event = dict(event)

    mapping = EVENT_STATE_MAP.get(event_id)

    if mapping is None:
        return False

    field, value = mapping
    previous = getattr(faults, field)

    setattr(faults, field, value)

    return previous != value


def apply_zone_event(
    zones: Mapping[int, Any],
    event: Mapping[str, Any],
) -> bool:
    """Apply a zone-specific FlexC EVENT to the matching zone state."""

    raw_event_id = event.get("EV_ID")
    raw_zone_id = event.get("ZONE_ID")

    try:
        event_id = int(str(raw_event_id))
        zone_id = int(str(raw_zone_id))
    except (TypeError, ValueError):
        return False

    # Zone tamper fault / restore.
    if event_id == 1008:
        value = True
    elif event_id == 1108:
        value = False
    else:
        return False

    zone = zones.get(zone_id)

    if zone is None:
        return False

    previous = zone.event_tamper

    zone.event_tamper = value
    zone.last_event = dict(event)

    return previous != value


def apply_panel_event(
    panel: Any,
    event: Mapping[str, Any],
) -> bool:
    """Apply a panel-level EVENT to PanelState."""

    raw_event_id = event.get("EV_ID")

    try:
        event_id = int(str(raw_event_id))
    except (TypeError, ValueError):
        return False

    mapping = PANEL_EVENT_STATE_MAP.get(event_id)

    if mapping is None:
        return False

    field, value = mapping
    previous = getattr(panel, field)

    setattr(panel, field, value)

    return previous != value


def apply_xbus_event(
    devices: dict[int, XBusDeviceState],
    event: Mapping[str, Any],
) -> bool:
    """Apply an X-BUS device EVENT to persistent device state."""

    raw_event_id = event.get("EV_ID")
    raw_device_id = event.get("KEYPAD_ID")

    try:
        event_id = int(str(raw_event_id))
        device_id = int(str(raw_device_id))
    except (TypeError, ValueError):
        return False

    # Validated X-BUS keypad tamper events:
    #
    # 5312 = physical tamper fault
    # 5316 = fault isolated by a user
    # 5317 = isolation restored / removed
    #
    # IMPORTANT:
    # 5317 does NOT mean the physical tamper fault is cleared.
    if event_id not in {5312, 5316, 5317}:
        return False

    device = devices.get(device_id)

    if device is None:
        raw_sia_address = event.get("SIA_ADDRESS")

        try:
            sia_address = (
                int(str(raw_sia_address)) if raw_sia_address is not None else None
            )
        except (TypeError, ValueError):
            sia_address = None

        device = XBusDeviceState(
            device_id=device_id,
            name=(
                str(event["KEYPAD_NAME"])
                if event.get("KEYPAD_NAME") is not None
                else None
            ),
            sia_address=sia_address,
        )

        devices[device_id] = device

    changed = False

    # Refresh descriptive metadata whenever SPC provides it.
    raw_name = event.get("KEYPAD_NAME")

    if raw_name is not None:
        name = str(raw_name)

        if device.name != name:
            device.name = name
            changed = True

    raw_sia_address = event.get("SIA_ADDRESS")

    if raw_sia_address is not None:
        try:
            sia_address = int(str(raw_sia_address))
        except (TypeError, ValueError):
            sia_address = None

        if sia_address is not None and device.sia_address != sia_address:
            device.sia_address = sia_address
            changed = True

    if event_id == 5312:
        if device.tamper_fault is not True:
            device.tamper_fault = True
            changed = True

    elif event_id == 5316:
        if device.tamper_isolated is not True:
            device.tamper_isolated = True
            changed = True

    elif event_id == 5317 and device.tamper_isolated is not False:
        device.tamper_isolated = False
        changed = True

    device.last_event = dict(event)
    device.updated_at = datetime.now(UTC)

    return changed


def apply_area_event(
    areas: Mapping[int, Any],
    event: Mapping[str, Any],
) -> bool:
    """Apply a validated area mode EVENT to the matching area."""

    raw_event_id = event.get("EV_ID")
    raw_area_id = event.get("AREA_ID")

    try:
        event_id = int(str(raw_event_id))
        area_id = int(str(raw_area_id))
    except (TypeError, ValueError):
        return False

    mode = AREA_EVENT_MODE_MAP.get(event_id)

    if mode is None:
        return False

    area = areas.get(area_id)

    if area is None:
        return False

    previous = area.mode
    area.mode = mode

    return previous != mode
