"""Regression tests for SPC door event diagnostic descriptions."""

from custom_components.spc_flexc.flexc.event_table import display_event_description


def test_door_event_descriptions_cover_spc_table():
    """All door event IDs 3000-3016 have the expected English labels."""
    expected = {
        3000: "Entry granted",
        3001: "Entry denied",
        3002: "Exit granted",
        3003: "Exit denied",
        3004: "Door open too long",
        3005: "Door left open",
        3006: "Door forced",
        3007: "Door normal",
        3008: "Door locked (access denied)",
        3009: "Door unlocked (free access)",
        3010: "Door opened",
        3011: "Door closed",
        3012: "Door release (DRS)",
        3013: "Door alarm restored",
        3014: "Unknown card",
        3015: "Reader locked",
        3016: "Reader unlocked",
    }
    assert {
        event_id: display_event_description(event_id) for event_id in range(3000, 3017)
    } == expected
