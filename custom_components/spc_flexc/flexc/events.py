"""Persistent state mapping for proven EVENT 0x60 pairs.

Only add IDs after validating the exact fault/restoration pair from SPC
documentation or a captured event.
"""

EVENT_STATE_MAP: dict[int, tuple[str, bool]] = {
    # Intentionally conservative. Populate exact validated pairs here.
}


def apply_event(faults, event):
    event_id = event.get("EV_ID")
    faults.last_event = event
    mapping = EVENT_STATE_MAP.get(event_id)
    if mapping:
        field, value = mapping
        setattr(faults, field, value)
