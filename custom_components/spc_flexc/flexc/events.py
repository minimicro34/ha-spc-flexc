"""FlexC EVENT 0x60 parsing and persistent fault mapping."""

from __future__ import annotations

import html
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from typing import Any

from ..models import FaultState

EVENT_STATE_MAP: dict[int, tuple[str, bool]] = {
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
