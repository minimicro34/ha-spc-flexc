"""Regression tests for the shared event catalogue."""

from custom_components.spc_flexc.flexc.event_table import (
    EVENT_TABLE,
    FLEXC_EVENT_DESCRIPTIONS,
    display_event_description,
    event_description,
)


def test_catalogue_display_labels():
    assert len(EVENT_TABLE) == 608
    assert set(FLEXC_EVENT_DESCRIPTIONS) == set(EVENT_TABLE)
    assert sum(
        info.display_description is not None for info in EVENT_TABLE.values()
    ) == 119
    for event_id, info in EVENT_TABLE.items():
        assert info.display_description is None or info.display_description != info.en
        assert event_description(event_id) == info.en
        assert display_event_description(event_id) == FLEXC_EVENT_DESCRIPTIONS[event_id]
    assert display_event_description(2100) == "Zone input active"
    assert display_event_description(3004) == "Door open too long"
    assert display_event_description(3010) == "Door opened"
    assert display_event_description(None) is None
    assert display_event_description(-1) is None
