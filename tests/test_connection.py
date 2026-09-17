"""Tests for the FlexC transport client."""

import pytest
from homeassistant.const import CONF_HOST

from custom_components.spc_flexc.const import (
    CONF_COMMAND_PASSWORD,
    CONF_COMMAND_USERNAME,
    CONF_KEY,
    CONF_PORT,
    DEFAULT_PORT,
)
from custom_components.spc_flexc.flexc.connection import (
    FlexCClient,
    _be16,
    _be32,
    _put16,
    _put32,
)


def _config(key: str | bytes, *, port: int | None = 52000) -> dict[str, object]:
    config: dict[str, object] = {
        CONF_HOST: "192.0.2.10",
        CONF_KEY: key,
        CONF_COMMAND_USERNAME: "HomeAssistant",
        CONF_COMMAND_PASSWORD: "password",
    }
    if port is not None:
        config[CONF_PORT] = port
    return config


def test_integer_wire_helpers() -> None:
    """FlexC integer helpers use big-endian wire encoding."""
    assert _be16(b"\x12\x34") == 0x1234
    assert _be32(b"\x12\x34\x56\x78") == 0x12345678
    assert _put16(0x1234) == b"\x12\x34"
    assert _put32(0x12345678) == b"\x12\x34\x56\x78"
    assert _put32(0x1_0000_0001) == b"\x00\x00\x00\x01"


def test_client_initialization_from_hex_key() -> None:
    """Client accepts the configured hexadecimal 32-byte encryption key."""
    client = FlexCClient(_config("11" * 32))

    assert client.host == "192.0.2.10"
    assert client.port == 52000
    assert client._key == bytes.fromhex("11" * 32)
    assert client.command_username == "HomeAssistant"
    assert client.command_password == "password"
    assert client.connected is False
    assert client._server is None
    assert client._reader is None
    assert client._writer is None
    assert client._closed is False
    assert client._last_message is None
    assert client._pending_reply is None
    assert client._poll_waiter is None
    assert client._response_length is None
    assert client._event_callback is None
    assert client._command_context is None


def test_client_initialization_accepts_bytes_and_default_port() -> None:
    """Client accepts a raw key and falls back to the FlexC default port."""
    client = FlexCClient(_config(b"\x22" * 32, port=None))

    assert client._key == b"\x22" * 32
    assert client.port == DEFAULT_PORT


@pytest.mark.parametrize("key", ["not-hexadecimal", "11" * 31, b"\x11" * 33])
def test_client_rejects_invalid_encryption_key(key: str | bytes) -> None:
    """Client rejects malformed or non-32-byte FlexC encryption keys."""
    with pytest.raises(ValueError, match="FlexC encryption key"):
        FlexCClient(_config(key))
