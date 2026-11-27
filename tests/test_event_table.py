"""Event descriptions from the panel's own complete event table."""

from custom_components.spc_flexc.flexc.event_table import EVENT_TABLE
from custom_components.spc_flexc.sensor import FLEXC_EVENT_DESCRIPTIONS


def test_every_panel_event_has_a_description() -> None:
    assert len(EVENT_TABLE) == 608
    assert all(FLEXC_EVENT_DESCRIPTIONS.get(event_id) for event_id in EVENT_TABLE)


def test_existing_descriptions_are_kept() -> None:
    assert FLEXC_EVENT_DESCRIPTIONS[3008] == "Door locked (access denied)"
    assert FLEXC_EVENT_DESCRIPTIONS[1200] == "Zone tamper [Alarm Zone]"
    assert FLEXC_EVENT_DESCRIPTIONS[1312] == "Zone tamper restored [Unused Zone]"


def test_door_opened_is_not_open_too_long() -> None:
    assert EVENT_TABLE[3010].en == "Door Open"
    assert EVENT_TABLE[3004].en == "Door Open too long"
    assert FLEXC_EVENT_DESCRIPTIONS[3010] == "Door opened"
    assert FLEXC_EVENT_DESCRIPTIONS[3004] == "Door open too long"


def test_zone_type_without_own_label_uses_the_panel_name() -> None:
    assert FLEXC_EVENT_DESCRIPTIONS[1216] == "Zone tamper [Lock Supervision Zone]"
    assert FLEXC_EVENT_DESCRIPTIONS[1305] == "Zone tamper restored [Line Zone]"
    assert FLEXC_EVENT_DESCRIPTIONS[1802] == "Zone trouble [Exit Term Zone]"
    assert FLEXC_EVENT_DESCRIPTIONS[1907] == "Zone trouble restored [Holdup Zone]"
    assert not any(
        description.startswith(("Zone tamper [Zone type", "Zone trouble [Zone type"))
        for event_id, description in FLEXC_EVENT_DESCRIPTIONS.items()
        if event_id in EVENT_TABLE
    )
