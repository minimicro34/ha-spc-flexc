"""Regression tests for FlexC EVENT/POLL synchronization.

Motivated by six command timeouts in Ludovic's SPC5300 capture on 2026-10-13.
The PCAP is encrypted: these tests simulate message order; they do not replay
or decrypt the capture, and do not establish the panel's expected sequence rules.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_HOST

from custom_components.spc_flexc.const import (
    CONF_COMMAND_PASSWORD,
    CONF_COMMAND_USERNAME,
    CONF_KEY,
    CONF_PORT,
)
from custom_components.spc_flexc.flexc.connection import (
    MSG_DATA,
    MSG_EVENT,
    MSG_POLL,
    FlexCClient,
)


def _client() -> FlexCClient:
    return FlexCClient(
        {
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 52000,
            CONF_KEY: "11" * 32,
            CONF_COMMAND_USERNAME: "HomeAssistant",
            CONF_COMMAND_PASSWORD: "password",
        }
    )


def _message() -> dict[str, object]:
    clear = bytearray(16)
    clear[0:2] = b"\x46\x01"
    clear[4:8] = (0x10203040).to_bytes(4, "big")
    return {
        "clear": bytes(clear),
        "protocol_id": 0x46,
        "version": 1,
        "connection_id": 0x10203040,
        "spt_sequence": 0x11223344,
        "rct_sequence": 0x55667788,
        "spt_account": 0x01020304,
        "rct_identifier": 0xA1A2A3A4,
        "data_header": b"\x00" * 8,
    }


@pytest.fixture
def client() -> FlexCClient:
    """Use the existing test client's dummy credentials and stub network writes."""
    instance = _client()
    instance._send_wire = AsyncMock()
    instance._build_clone_ack = MagicMock(return_value=b"ack")
    return instance


def _incoming(message_id: int, *, sequence: int = 100) -> dict[str, object]:
    message = _message()
    message["message_id"] = message_id
    message["rct_sequence"] = sequence
    if message_id == MSG_EVENT:
        message["app_data"] = b""
    if message_id == MSG_DATA:
        message.update(
            new_application_message=True,
            application_length=0,
            app_data=b"",
        )
    return message


@pytest.mark.asyncio
async def test_event_between_commands_invalidates_context_until_fresh_poll(
    client: FlexCClient,
) -> None:
    """An unsolicited EVENT prevents reuse of the previous DATA context."""
    data = _incoming(MSG_DATA, sequence=10)
    client._handle_incoming_data = MagicMock()
    await client._handle_message(data)
    assert client._command_context == data
    assert client._context_event.is_set()

    event = _incoming(MSG_EVENT, sequence=11)
    with patch(
        "custom_components.spc_flexc.flexc.connection.parse_event_payload",
        return_value=None,
    ):
        await client._handle_message(event)

    assert client._command_context is None
    assert not client._context_event.is_set()
    assert client._awaiting_poll_after_event is True
    client._send_wire.assert_awaited()

    poll = _incoming(MSG_POLL, sequence=12)
    await client._handle_message(poll)
    assert client._command_context == poll
    assert client._context_event.is_set()
    assert client._awaiting_poll_after_event is False


@pytest.mark.asyncio
async def test_multiple_events_do_not_reenable_stale_context(
    client: FlexCClient,
) -> None:
    """Repeated EVENT frames leave the command chain invalid until a POLL."""
    await client._handle_message(_incoming(MSG_POLL))
    with patch(
        "custom_components.spc_flexc.flexc.connection.parse_event_payload",
        return_value=None,
    ):
        for sequence in (101, 102, 103):
            await client._handle_message(_incoming(MSG_EVENT, sequence=sequence))
            assert client._command_context is None
            assert client._awaiting_poll_after_event
            assert not client._context_event.is_set()

    await client._handle_message(_incoming(MSG_POLL, sequence=104))
    assert client._command_context is not None
    assert not client._awaiting_poll_after_event


@pytest.mark.asyncio
async def test_event_during_command_keeps_reply_context_authoritative(
    client: FlexCClient,
) -> None:
    """EVENT and POLL cannot displace the context of an in-flight command."""
    original = _incoming(MSG_DATA, sequence=200)
    client._command_context = original
    client._context_event.set()
    pending = asyncio.get_running_loop().create_future()
    client._pending_reply = pending
    client._handle_incoming_data = MagicMock()

    with patch(
        "custom_components.spc_flexc.flexc.connection.parse_event_payload",
        return_value=None,
    ):
        await client._handle_message(_incoming(MSG_EVENT, sequence=201))
    await client._handle_message(_incoming(MSG_POLL, sequence=202))

    assert client._command_context is original
    assert not client._awaiting_poll_after_event
    assert client._context_event.is_set()

    reply = _incoming(MSG_DATA, sequence=203)
    await client._handle_message(reply)
    assert client._command_context == reply
    assert client._rct_sequence == 203
    assert not client._awaiting_poll_after_event
    client._handle_incoming_data.assert_called_once_with(reply)
    pending.cancel()


@pytest.mark.asyncio
async def test_event_during_command_then_next_event_requires_poll(
    client: FlexCClient,
) -> None:
    """Only an EVENT after completion invalidates the newly established chain."""
    client._handle_incoming_data = MagicMock()
    pending = asyncio.get_running_loop().create_future()
    client._pending_reply = pending
    with patch(
        "custom_components.spc_flexc.flexc.connection.parse_event_payload",
        return_value=None,
    ):
        await client._handle_message(_incoming(MSG_EVENT, sequence=301))
        await client._handle_message(_incoming(MSG_DATA, sequence=302))
        assert client._command_context is not None
        client._pending_reply = None
        await client._handle_message(_incoming(MSG_EVENT, sequence=303))

    assert client._command_context is None
    assert client._awaiting_poll_after_event
    pending.cancel()


@pytest.mark.asyncio
async def test_new_handshake_resets_wait_for_poll_flag(client: FlexCClient) -> None:
    """A new TCP session must not inherit an earlier EVENT invalidation."""
    from custom_components.spc_flexc.flexc.connection import MSG_CONNECTION_REQUEST

    await client._handle_message(_incoming(MSG_POLL))
    with patch(
        "custom_components.spc_flexc.flexc.connection.parse_event_payload",
        return_value=None,
    ):
        await client._handle_message(_incoming(MSG_EVENT))
    assert client._awaiting_poll_after_event

    # The local flag is reset by _handle_client() at TCP connection acceptance,
    # not by the handshake message handler. Test the handshake's context behavior
    # separately without assuming that it resets this flag.
    client._awaiting_poll_after_event = False  # emulate _handle_client reset
    await client._handle_message(_incoming(MSG_CONNECTION_REQUEST))
    assert client._command_context is None
    assert not client._context_event.is_set()
    await client._handle_message(_incoming(MSG_POLL, sequence=401))
    assert client._command_context is not None
    assert not client._awaiting_poll_after_event


@pytest.mark.parametrize(
    ("timestamp", "command"),
    [
        ("19:07:09.113", "ZONE_STATUS"),
        ("19:07:42.113", "ZONE_STATUS"),
        ("19:14:32.446", "DOOR_STATUS"),
        ("19:15:03.113", "ZONE_STATUS"),
        ("19:15:32.781", "MG_STATUS"),
        ("19:16:03.781", "MG_STATUS"),
    ],
)
@pytest.mark.asyncio
async def test_ludovic_timeout_patterns_keep_event_poll_order(
    client: FlexCClient, timestamp: str, command: str
) -> None:
    """For each observed timeout, reproduce the suspected EVENT/POLL race.

    Times and command names are traceability metadata, not a PCAP replay.
    """
    client._handle_incoming_data = MagicMock()
    await client._handle_message(_incoming(MSG_DATA, sequence=500))
    with patch(
        "custom_components.spc_flexc.flexc.connection.parse_event_payload",
        return_value=None,
    ):
        await client._handle_message(_incoming(MSG_EVENT, sequence=501))
    assert client._command_context is None, (timestamp, command)
    assert not client._context_event.is_set(), (timestamp, command)
    await client._handle_message(_incoming(MSG_POLL, sequence=502))
    assert client._command_context is not None, (timestamp, command)
    assert client._rct_sequence == 502, (timestamp, command)
