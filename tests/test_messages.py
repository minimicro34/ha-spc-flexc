"""Tests for FlexC protocol message constants."""

from custom_components.spc_flexc.flexc import messages


def test_flexc_message_type_constants() -> None:
    """FlexC wire message types keep their protocol-defined values."""
    assert messages.MSG_CONNECTION_REQUEST == 0x02
    assert messages.MSG_CONNECTION_ACK == 0x03
    assert messages.MSG_POLL == 0x20
    assert messages.MSG_POLL_ACK == 0x21
    assert messages.MSG_EVENT == 0x60
    assert messages.MSG_EVENT_ACK == 0x61
    assert messages.MSG_DATA == 0x80
    assert messages.MSG_DATA_ACK == 0x81
    assert messages.MSG_ERROR == 0xFF
