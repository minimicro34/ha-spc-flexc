"""Focused regression tests for timeout-only FlexC command diagnostics."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.spc_flexc.const import (
    CONF_COMMAND_PASSWORD,
    CONF_COMMAND_USERNAME,
    CONF_KEY,
)
from custom_components.spc_flexc.flexc.connection import (
    MSG_DATA,
    MSG_DATA_ACK,
    MSG_EVENT,
    MSG_POLL,
    FlexCClient,
    _CommandTrace,
)


def _client() -> FlexCClient:
    return FlexCClient(
        {
            "host": "192.0.2.10",
            CONF_KEY: "11" * 32,
            CONF_COMMAND_USERNAME: "test-user",
            CONF_COMMAND_PASSWORD: "secret-password",
        }
    )


def test_trace_is_bounded_and_relative() -> None:
    trace = _CommandTrace(1, "CMD_TEST", 2, 100.0)
    for index in range(30):
        trace.record("DATA_ACK", 100.0 + index / 1000)
    assert len(trace.timeline) == 24
    assert trace.timeline[0] == "0ms:DATA_ACK"
    assert trace.timeline[-1] == "23ms:DATA_ACK"


@pytest.mark.asyncio
async def test_trace_counts_ack_data_event_and_poll_without_logging(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _client()
    client._send_wire = AsyncMock()
    client._build_clone_ack = MagicMock(return_value=b"ack")
    client._handle_incoming_data = MagicMock()
    trace = _CommandTrace(7, "CMD_TEST", 3, asyncio.get_running_loop().time())
    client._active_trace = trace
    client._pending_reply = asyncio.get_running_loop().create_future()
    client._command_context = {"rct_sequence": 1}

    with caplog.at_level(logging.WARNING):
        for message_id in (MSG_DATA_ACK, MSG_EVENT, MSG_POLL, MSG_DATA):
            message = {
                "message_id": message_id,
                "rct_sequence": 2,
                "app_data": b"",
            }
            await client._handle_message(message)

    assert trace.ack_at is not None
    assert trace.data_first_at is not None
    assert trace.data_last_at is not None
    assert trace.data_frames == 1
    assert trace.events == 1
    assert trace.polls == 1
    assert [item.split(":")[1] for item in trace.timeline] == [
        "DATA_ACK",
        "EVENT",
        "POLL",
        "DATA",
    ]
    assert not caplog.records
    client._pending_reply.cancel()


@pytest.mark.asyncio
async def test_timeout_summary_is_warning_and_never_exposes_credentials(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _client()
    now = asyncio.get_running_loop().time()
    trace = _CommandTrace(12, "CMD_STATUS_ZONE", 5, now - 15)
    trace.sent_at = now - 14
    trace.ack_at = now - 13
    trace.events = 2
    trace.record("DATA_ACK", now - 13)
    client._response_buffer = bytearray(b"partial")
    client._response_length = 100
    client._pending_reply = asyncio.get_running_loop().create_future()

    with caplog.at_level(logging.WARNING):
        client._log_command_timeout(trace)

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelno == logging.WARNING
    assert "command_id=12" in record.message
    assert "command=CMD_STATUS_ZONE" in record.message
    assert "session=5" in record.message
    assert "events=2" in record.message
    assert "response_bytes=7" in record.message
    assert "expected_bytes=100" in record.message
    assert "secret-password" not in record.message
    assert "test-user" not in record.message
    client._pending_reply.cancel()


@pytest.mark.asyncio
async def test_command_timeout_emits_diagnostic_and_resets_session(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A real command timeout emits diagnostics and preserves recovery behavior."""
    from unittest.mock import patch

    from custom_components.spc_flexc.flexc.connection import (
        FlexCCommandTimeout,
    )

    client = _client()
    client.connected = True
    client._session_generation = 4
    client._command_context = {"rct_sequence": 1}
    client.async_ensure_connected = AsyncMock()
    client._build_application_buffer = MagicMock(return_value=b"application")
    client._build_outbound_data = MagicMock(return_value=b"wire")
    client._send_wire = AsyncMock()
    writer = MagicMock()
    writer.wait_closed = AsyncMock()
    client._writer = writer

    with (
        patch("custom_components.spc_flexc.flexc.connection.COMMAND_TIMEOUT", 0),
        caplog.at_level(logging.WARNING),
        pytest.raises(FlexCCommandTimeout, match="Timeout waiting"),
    ):
        await client.async_send_flexml(
            '<CMD_STATUS_ZONE USER="test-user" PASSWORD="secret-password" />'
        )

    diagnostics = [
        record
        for record in caplog.records
        if record.message.startswith("FlexC timeout diagnostic:")
    ]
    assert len(diagnostics) == 1
    assert "command=CMD_STATUS_ZONE" in diagnostics[0].message
    assert "session=4" in diagnostics[0].message
    assert "SENT" in diagnostics[0].message
    assert "secret-password" not in caplog.text
    assert "test-user" not in caplog.text
    assert client._active_trace is None
    assert client._pending_reply is None
    assert client._command_context is None
    assert not client.connected
    writer.close.assert_called_once_with()
    writer.wait_closed.assert_awaited_once_with()
