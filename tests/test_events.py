from custom_components.spc_flexc.flexc.events import (
    apply_event,
    parse_event_payload,
)
from custom_components.spc_flexc.models import FaultState


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

    assert faults.modem_1_fault is None
    assert faults.modem_1_line_fault is None
    assert faults.rf_jamming is None
    assert faults.xbus_mains_fault is None
    assert faults.xbus_battery_fault is None


def test_invalid_event_id() -> None:
    """Test an invalid event ID."""
    faults = FaultState()

    assert apply_event(faults, {"EV_ID": "invalid"}) is False
