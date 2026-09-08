"""Tests for SPC FlexC door-status handling."""

from custom_components.spc_flexc.zone_control_coordinator import (
    _door_state_from_status,
)


def test_door_state_preserves_real_spc5320_fields() -> None:
    """Real SPC5320 door fields must be exposed without guessing mode semantics."""
    door = _door_state_from_status(
        {
            "DOOR_ID": "1",
            "DPS_INPUT": "1",
            "DRS_INPUT": "1",
            "STATUS": "0",
            "MODE": "2",
            "READER1_FORMAT": "255",
            "READER2_FORMAT": "255",
            "ZONE_ID": "17",
            "ZONE_NAME": "Entrée Garage",
            "AREA_ID": "2",
            "AREA_NAME": "Garage",
            "AREA_SIDE_1": "3",
            "AREA_SIDE_1_NAME": "Studio",
            "ENTRY_EXIT": "1",
            "NORMAL_ALLOWED": "1",
            "LOCK_ALLOWED": "1",
        }
    )

    assert door.door_id == 1
    assert door.name == "Entrée Garage"
    assert door.status == 0
    assert door.mode == 2
    assert door.dps_input == 1
    assert door.drs_input == 1
    assert door.zone_id == 17
    assert door.zone_name == "Entrée Garage"
    assert door.area_id == 2
    assert door.area_name == "Garage"
    assert door.area_side_1 == 3
    assert door.area_side_1_name == "Studio"
    assert door.entry_exit is True
    assert door.normal_allowed is True
    assert door.lock_allowed is True
    assert door.raw["MODE"] == "2"
