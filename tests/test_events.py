from custom_components.spc_flexc.flexc.events import (
    apply_event,
    apply_panel_event,
    apply_xbus_event,
    apply_zone_event,
    parse_event_payload,
)
from custom_components.spc_flexc.models import (
    FaultState,
    PanelState,
    XBusDeviceState,
    ZoneState,
)


def test_parse_event_payload() -> None:
    """Test parsing a FlexC EVENT payload."""
    payload = b'<EVENT EV_ID="5336" EV_NAME="RF jamming" />\x00\x00'

    event = parse_event_payload(payload)

    assert event is not None
    assert event["EV_ID"] == "5336"
    assert event["EV_NAME"] == "RF jamming"


def test_parse_invalid_event_payload() -> None:
    """Test invalid EVENT payload."""
    assert parse_event_payload(b"not xml\x00") is None


def test_modem_fault_events() -> None:
    """Test modem fault and restore events."""
    faults = FaultState()

    assert apply_event(faults, {"EV_ID": "6100"}) is True
    assert faults.modem_1_fault is True

    assert apply_event(faults, {"EV_ID": "6101"}) is True
    assert faults.modem_1_fault is False


def test_modem_line_fault_events() -> None:
    """Test modem line fault and restore events."""
    faults = FaultState()

    assert apply_event(faults, {"EV_ID": "6106"}) is True
    assert faults.modem_1_line_fault is True

    assert apply_event(faults, {"EV_ID": "6107"}) is True
    assert faults.modem_1_line_fault is False


def test_xbus_mains_fault_events() -> None:
    """Test X-BUS mains fault and restore events."""
    faults = FaultState()

    assert apply_event(faults, {"EV_ID": "5324"}) is True
    assert faults.xbus_mains_fault is True

    assert apply_event(faults, {"EV_ID": "5325"}) is True
    assert faults.xbus_mains_fault is False


def test_xbus_battery_fault_events() -> None:
    """Test X-BUS battery fault and restore events."""
    faults = FaultState()

    assert apply_event(faults, {"EV_ID": "5330"}) is True
    assert faults.xbus_battery_fault is True

    assert apply_event(faults, {"EV_ID": "5331"}) is True
    assert faults.xbus_battery_fault is False


def test_rf_jamming_events() -> None:
    """Test RF jamming and restore events."""
    faults = FaultState()

    assert apply_event(faults, {"EV_ID": "5336"}) is True
    assert faults.rf_jamming is True

    assert apply_event(faults, {"EV_ID": "5337"}) is True
    assert faults.rf_jamming is False


def test_unknown_event() -> None:
    """Test that an unknown event does not alter fault state."""
    faults = FaultState()

    assert apply_event(faults, {"EV_ID": "9999"}) is False

    assert faults.mains_fault is None
    assert faults.battery_fault is None
    assert faults.panel_tamper is None
    assert faults.modem_1_fault is None
    assert faults.modem_1_line_fault is None
    assert faults.rf_jamming is None
    assert faults.xbus_mains_fault is None
    assert faults.xbus_battery_fault is None


def test_invalid_event_id() -> None:
    """Test an invalid event ID."""
    faults = FaultState()

    assert apply_event(faults, {"EV_ID": "invalid"}) is False


def test_panel_mains_fault_events() -> None:
    """Test panel 230 V mains fault and restore events."""
    faults = FaultState()

    assert apply_event(faults, {"EV_ID": "5000"}) is True
    assert faults.mains_fault is True

    assert apply_event(faults, {"EV_ID": "5001"}) is True
    assert faults.mains_fault is False


def test_panel_battery_fault_events() -> None:
    """Test panel battery fault and restore events."""
    faults = FaultState()

    assert apply_event(faults, {"EV_ID": "5006"}) is True
    assert faults.battery_fault is True

    assert apply_event(faults, {"EV_ID": "5007"}) is True
    assert faults.battery_fault is False


def test_panel_tamper_events() -> None:
    """Test panel enclosure tamper fault and restore events."""
    faults = FaultState()

    assert apply_event(faults, {"EV_ID": "5206"}) is True
    assert faults.panel_tamper is True

    assert apply_event(faults, {"EV_ID": "5207"}) is True
    assert faults.panel_tamper is False


def test_engineer_mode_events() -> None:
    """Test engineer mode event updates."""
    panel = PanelState()

    assert apply_panel_event(panel, {"EV_ID": "7003"}) is True
    assert panel.engineer_mode is True

    assert apply_panel_event(panel, {"EV_ID": "7004"}) is True
    assert panel.engineer_mode is False


def test_zone_tamper_events() -> None:
    """Test zone tamper fault and restore events."""
    zone = ZoneState(
        zone_id=7,
        name="AP sirene intéri",
        area_id=1,
    )
    zones = {7: zone}

    fault_event = {
        "EV_ID": "1008",
        "ZONE_ID": "7",
        "AREA_ID": "1",
        "ZONE_NAME": "AP sirene intéri",
        "SIA_CODE": "TA",
    }

    assert apply_zone_event(zones, fault_event) is True
    assert zone.event_tamper is True
    assert zone.last_event == fault_event

    restore_event = {
        "EV_ID": "1108",
        "ZONE_ID": "7",
        "AREA_ID": "1",
        "ZONE_NAME": "AP sirene intéri",
        "SIA_CODE": "TR",
    }

    assert apply_zone_event(zones, restore_event) is True
    assert zone.event_tamper is False
    assert zone.last_event == restore_event


def test_zone_tamper_unknown_zone_is_ignored() -> None:
    """Test that a tamper event for an unknown zone is ignored."""
    zones: dict[int, ZoneState] = {}

    assert (
        apply_zone_event(
            zones,
            {
                "EV_ID": "1008",
                "ZONE_ID": "7",
            },
        )
        is False
    )

    assert zones == {}


def test_xbus_tamper_fault_creates_device() -> None:
    """Test creation of an X-BUS device from a tamper fault event."""
    devices: dict[int, XBusDeviceState] = {}

    event = {
        "EV_ID": "5312",
        "KEYPAD_ID": "1",
        "KEYPAD_NAME": "CLA 1",
        "SIA_ADDRESS": "1",
        "SIA_CODE": "ES",
        "CID_CODE": "341",
        "CID_QUAL": "1",
    }

    assert apply_xbus_event(devices, event) is True

    assert 1 in devices

    device = devices[1]

    assert device.device_id == 1
    assert device.name == "CLA 1"
    assert device.sia_address == 1
    assert device.tamper_fault is True
    assert device.tamper_isolated is None
    assert device.last_event == event
    assert device.updated_at is not None


def test_xbus_tamper_isolation_cycle() -> None:
    """Test X-BUS tamper isolation without clearing the physical fault."""
    devices: dict[int, XBusDeviceState] = {}

    assert (
        apply_xbus_event(
            devices,
            {
                "EV_ID": "5312",
                "KEYPAD_ID": "1",
                "KEYPAD_NAME": "CLA 1",
                "SIA_ADDRESS": "1",
            },
        )
        is True
    )

    device = devices[1]

    assert device.tamper_fault is True
    assert device.tamper_isolated is None

    assert (
        apply_xbus_event(
            devices,
            {
                "EV_ID": "5316",
                "KEYPAD_ID": "1",
                "KEYPAD_NAME": "CLA 1",
            },
        )
        is True
    )

    assert device.tamper_fault is True
    assert device.tamper_isolated is True

    assert (
        apply_xbus_event(
            devices,
            {
                "EV_ID": "5317",
                "KEYPAD_ID": "1",
                "KEYPAD_NAME": "CLA 1",
            },
        )
        is True
    )

    assert device.tamper_isolated is False

    # 5317 means isolation restored/removed.
    # It must NOT clear the physical X-BUS tamper fault.
    assert device.tamper_fault is True
