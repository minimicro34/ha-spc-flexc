"""Tests for the FlexC transport client."""

import asyncio
import hashlib
import zlib
from unittest.mock import AsyncMock, MagicMock, patch

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
    MSG_CONNECTION_ACK_LEGACY,
    MSG_DATA,
    PROTOCOL_ID,
    PROTOCOL_VERSION,
    RCT_CONNECTION_ID,
    FlexCClient,
    FlexCConnectionError,
    FlexCProtocolError,
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


def _client() -> FlexCClient:
    return FlexCClient(_config("11" * 32))


def _message() -> dict[str, object]:
    clear = bytearray(16)
    clear[0] = PROTOCOL_ID
    clear[1] = PROTOCOL_VERSION
    clear[4:8] = _put32(0x10203040)
    return {
        "clear": bytes(clear),
        "protocol_id": PROTOCOL_ID,
        "version": PROTOCOL_VERSION,
        "connection_id": 0x10203040,
        "spt_sequence": 0x11223344,
        "rct_sequence": 0x55667788,
        "spt_account": 0x01020304,
        "rct_identifier": 0xA1A2A3A4,
        "data_header": b"\x00" * 8,
    }


def test_integer_wire_helpers() -> None:
    """FlexC integer helpers use big-endian wire encoding."""
    assert _be16(b"\x12\x34") == 0x1234
    assert _be32(b"\x12\x34\x56\x78") == 0x12345678
    assert _put16(0x1234) == b"\x12\x34"
    assert _put32(0x12345678) == b"\x12\x34\x56\x78"
    assert _put32(0x1_0000_0001) == b"\x00\x00\x00\x01"


def test_client_initialization_from_hex_key() -> None:
    """Client accepts the configured hexadecimal 32-byte encryption key."""
    client = _client()

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


@pytest.mark.asyncio
async def test_ensure_connected_returns_when_session_is_ready() -> None:
    """An established session needs no listener or wait."""
    client = _client()
    client.connected = True
    client._writer = MagicMock()
    client._start_server = AsyncMock()

    await client.async_ensure_connected()

    client._start_server.assert_not_awaited()


@pytest.mark.asyncio
async def test_ensure_connected_starts_listener_and_waits_for_panel() -> None:
    """A disconnected client starts its receiver and waits for the panel."""
    client = _client()

    async def start_server() -> None:
        client._server = MagicMock()
        client._connected_event.set()

    client._start_server = AsyncMock(side_effect=start_server)

    await client.async_ensure_connected()

    client._start_server.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_ensure_connected_times_out() -> None:
    """Failure of the panel to establish its reverse connection is explicit."""
    client = _client()
    client._server = MagicMock()

    with patch(
        "custom_components.spc_flexc.flexc.connection.CONNECT_TIMEOUT", 0
    ), pytest.raises(FlexCConnectionError, match="did not connect"):
        await client.async_ensure_connected()


@pytest.mark.asyncio
async def test_start_server_rejects_closed_client() -> None:
    """A closed transport cannot be restarted."""
    client = _client()
    client._closed = True

    with pytest.raises(FlexCConnectionError, match="closed"):
        await client._start_server()


@pytest.mark.asyncio
async def test_start_server_binds_configured_port() -> None:
    """The receiver binds all interfaces on the configured FlexC port."""
    client = _client()
    socket = MagicMock()
    socket.getsockname.return_value = ("0.0.0.0", 52000)
    server = MagicMock()
    server.sockets = [socket]

    with patch(
        "custom_components.spc_flexc.flexc.connection.asyncio.start_server",
        new=AsyncMock(return_value=server),
    ) as start_server:
        await client._start_server()

    assert client._server is server
    start_server.assert_awaited_once_with(
        client._handle_client, host="0.0.0.0", port=52000
    )


@pytest.mark.asyncio
async def test_handle_client_rejects_unexpected_host() -> None:
    """Only the configured SPC address may establish the FlexC session."""
    client = _client()
    reader = MagicMock()
    writer = MagicMock()
    writer.get_extra_info.return_value = ("192.0.2.99", 12345)
    writer.wait_closed = AsyncMock()

    await client._handle_client(reader, writer)

    writer.close.assert_called_once_with()
    writer.wait_closed.assert_awaited_once_with()
    assert client._writer is None


@pytest.mark.asyncio
async def test_handle_client_cleans_up_closed_session_and_pending_reply() -> None:
    """Peer disconnect clears transport state and fails an outstanding reply."""
    client = _client()
    reader = MagicMock()
    reader.readexactly = AsyncMock(side_effect=asyncio.IncompleteReadError(b"", 16))
    writer = MagicMock()
    writer.get_extra_info.return_value = ("192.0.2.10", 12345)
    writer.wait_closed = AsyncMock()
    pending = asyncio.get_running_loop().create_future()
    client._pending_reply = pending

    await client._handle_client(reader, writer)

    assert client.connected is False
    assert client._reader is None
    assert client._writer is None
    assert client._pending_reply is None
    assert isinstance(pending.exception(), FlexCConnectionError)
    writer.close.assert_called_once_with()
    writer.wait_closed.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_read_frame_validates_protocol_and_version() -> None:
    """Malformed clear headers are rejected before reading an encrypted body."""
    client = _client()

    for header, expected in (
        (bytes((0, PROTOCOL_VERSION)) + b"\x00" * 14, "protocol ID"),
        (bytes((PROTOCOL_ID, 0)) + b"\x00" * 14, "version"),
    ):
        reader = MagicMock()
        reader.readexactly = AsyncMock(return_value=header)
        with pytest.raises(FlexCProtocolError, match=expected):
            await client._read_frame(reader)


@pytest.mark.asyncio
async def test_read_frame_reads_complete_minimum_frame() -> None:
    """A zero-unit frame consists of its 16-byte header plus 48-byte body."""
    client = _client()
    header = bytes((PROTOCOL_ID, PROTOCOL_VERSION, 0, 0)) + b"\x00" * 12
    body = b"\xaa" * 48
    reader = MagicMock()
    reader.readexactly = AsyncMock(side_effect=[header, body])

    assert await client._read_frame(reader) == header + body
    assert reader.readexactly.await_args_list[1].args == (48,)


def test_parse_frame_rejects_invalid_encrypted_length() -> None:
    """Encrypted frames must respect the FlexC block layout."""
    client = _client()

    with pytest.raises(FlexCProtocolError, match="Invalid encrypted"):
        client._parse_frame(b"\x00" * 63)


def test_digest_and_encryption_round_trip() -> None:
    """Encrypted frames decrypt with the validated digest intact."""
    client = _client()
    clear = bytes((PROTOCOL_ID, PROTOCOL_VERSION)) + b"\x00" * 14
    plain = bytearray(48)
    plain[18] = 0x21

    wire = client._encrypt_message(clear, plain)
    parsed = client._parse_frame(wire)

    assert parsed["message_id"] == 0x21
    assert parsed["sha1_ok"] is True
    logical = bytearray(clear + parsed["plain"])
    logical[44:64] = b"\x00" * 20
    assert parsed["recv_sha1"] == hashlib.sha1(logical).digest()


def test_build_connection_ack_preserves_validated_fields() -> None:
    """Legacy connection ACK contains the expected session identifiers."""
    client = _client()
    request = _message()

    parsed = client._parse_frame(client._build_connection_ack(request))

    assert parsed["message_id"] == MSG_CONNECTION_ACK_LEGACY
    assert parsed["connection_id"] == RCT_CONNECTION_ID
    assert parsed["spt_sequence"] == request["spt_sequence"]
    assert parsed["rct_identifier"] == request["rct_identifier"]
    assert parsed["sha1_ok"] is True


def test_build_clone_ack_preserves_session_fields() -> None:
    """Clone ACK keeps the incoming FlexC session and sequence values."""
    client = _client()
    request = _message()

    parsed = client._parse_frame(client._build_clone_ack(request, 0x21))

    assert parsed["message_id"] == 0x21
    assert parsed["connection_id"] == request["connection_id"]
    assert parsed["spt_sequence"] == request["spt_sequence"]
    assert parsed["rct_sequence"] == request["rct_sequence"]
    assert parsed["spt_account"] == request["spt_account"]
    assert parsed["rct_identifier"] == request["rct_identifier"]
    assert parsed["sha1_ok"] is True


def test_build_application_buffer_metadata_and_alignment() -> None:
    """Application buffer carries exact FLEXML length/CRC and block alignment."""
    client = _client()
    command = '<FLEXML><COMMAND TYPE="TEST" /></FLEXML>'
    command_bytes = command.encode("ascii")

    with patch(
        "custom_components.spc_flexc.flexc.connection.os.urandom",
        side_effect=lambda length: b"\xaa" * length,
    ):
        application = client._build_application_buffer(command)

    header, payload = application.split(b"\x00", 1)
    assert len(application) % 16 == 0
    assert f'XML_LEN="{len(command_bytes)}"'.encode() in header
    assert f'XML_CLEN="{len(command_bytes)}"'.encode() in header
    assert f'XML_CRC="{zlib.crc32(command_bytes) & 0xFFFFFFFF}"'.encode() in header
    assert payload.startswith(command_bytes + b"\x00")


def test_build_application_buffer_rejects_non_ascii_command() -> None:
    """FLEXML wire commands are explicitly restricted to ASCII."""
    client = _client()

    with pytest.raises(FlexCProtocolError, match="ASCII"):
        client._build_application_buffer("<FLEXML>é</FLEXML>")


def test_build_outbound_data_contains_application() -> None:
    """Outbound DATA advertises and carries the complete application buffer."""
    client = _client()
    request = _message()
    application = b"A" * 32

    parsed = client._parse_frame(
        client._build_outbound_data(request, 0x12345679, application)
    )

    assert parsed["message_id"] == MSG_DATA
    assert parsed["length_units"] == 2
    assert parsed["application_length"] == len(application)
    assert parsed["new_application_message"] is True
    assert parsed["rct_sequence"] == 0x12345679
    assert parsed["app_data"] == application
    assert parsed["sha1_ok"] is True


@pytest.mark.asyncio
async def test_send_wire_requires_active_connection_and_writes_frame() -> None:
    """Wire writes fail without a session and drain an active writer."""
    client = _client()

    with pytest.raises(FlexCConnectionError, match="No active"):
        await client._send_wire(b"frame")

    closing_writer = MagicMock()
    closing_writer.is_closing.return_value = True
    client._writer = closing_writer
    with pytest.raises(FlexCConnectionError, match="No active"):
        await client._send_wire(b"frame")

    writer = MagicMock()
    writer.is_closing.return_value = False
    writer.drain = AsyncMock()
    client._writer = writer

    await client._send_wire(b"frame")

    writer.write.assert_called_once_with(b"frame")
    writer.drain.assert_awaited_once_with()
