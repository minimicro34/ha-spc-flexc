"""DATA acknowledgements for replies longer than one chunk."""

from custom_components.spc_flexc.flexc.connection import (
    REPLY_CHUNK_LENGTH,
    _chunk_ack_source,
)


def _message(application_length: int) -> dict:
    return {
        "application_length": application_length,
        "data_header": application_length.to_bytes(4, "big") + b"\x01\x00\x00\x00",
        "spt_sequence": 7,
    }


def test_long_reply_ack_carries_one_chunk_length() -> None:
    ack = _chunk_ack_source(_message(21117))
    assert ack["data_header"][0:4] == REPLY_CHUNK_LENGTH.to_bytes(4, "big")
    assert ack["data_header"][4:] == b"\x01\x00\x00\x00"
    assert ack["spt_sequence"] == 7


def test_short_reply_ack_is_unchanged() -> None:
    message = _message(518)
    assert _chunk_ack_source(message)["data_header"] == message["data_header"]


def test_message_without_data_header_is_passed_through() -> None:
    assert _chunk_ack_source({"spt_sequence": 1}) == {"spt_sequence": 1}


def test_ack_carries_cumulative_length() -> None:
    message = _message(25000)
    ack = _chunk_ack_source(message, 20480)
    assert ack["data_header"][0:4] == (20480).to_bytes(4, "big")


def _counter():
    from unittest.mock import MagicMock

    from custom_components.spc_flexc.flexc.connection import FlexCClient

    client = MagicMock(spec=FlexCClient)
    client._ack_total = None
    client._ack_received = 0
    client._ack_last_part = None
    return client, FlexCClient._count_data_part


def _part(seq: int, data: bytes, *, start: bool, total: int = 25000) -> dict:
    return {
        "spt_sequence": seq,
        "application_length": total if start else REPLY_CHUNK_LENGTH,
        "new_application_message": start,
        "app_data": data,
    }


def test_count_data_part_counts_parts_up_to_total() -> None:
    client, count = _counter()
    parts = (
        _part(1, b"a" * REPLY_CHUNK_LENGTH, start=True),
        _part(2, b"b" * REPLY_CHUNK_LENGTH, start=False),
        _part(3, b"c" * 4520, start=False),
    )
    assert [count(client, p) for p in parts] == [
        (10240, False),
        (20480, False),
        (25000, False),
    ]
    # A new message starts counting again.
    assert count(client, _part(4, b"x" * 512, start=True, total=500)) == (500, False)


def test_count_data_part_unknown_without_start() -> None:
    client, count = _counter()
    assert count(client, _part(1, b"", start=False)) == (None, False)


def test_repeated_part_does_not_advance_the_ack() -> None:
    """The same part sent again gets the same ACK and is marked as a repeat."""
    client, count = _counter()
    first = _part(1, b"a" * REPLY_CHUNK_LENGTH, start=True)
    second = _part(2, b"b" * REPLY_CHUNK_LENGTH, start=False)
    assert count(client, first) == (10240, False)
    assert count(client, second) == (20480, False)
    assert count(client, second) == (20480, True)
    assert count(client, _part(3, b"c" * 4520, start=False)) == (25000, False)


def test_same_data_in_a_new_part_is_counted() -> None:
    """Only the same SPT sequence with the same data is a repeat."""
    client, count = _counter()
    data = b"a" * REPLY_CHUNK_LENGTH
    assert count(client, _part(1, data, start=True)) == (10240, False)
    assert count(client, _part(2, data, start=False)) == (20480, False)


def test_repeated_first_part_restarts_the_message() -> None:
    """A first part sent again starts the message again; the ACK stays one part."""
    client, count = _counter()
    first = _part(1, b"a" * REPLY_CHUNK_LENGTH, start=True)
    assert count(client, first) == (10240, False)
    assert count(client, first) == (10240, False)


async def test_three_part_reply_is_acknowledged_cumulatively_and_reassembled() -> None:
    """A 25000-byte reply in three DATA parts: each ACK carries bytes so far."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from custom_components.spc_flexc.flexc.connection import MSG_DATA, FlexCClient

    client = FlexCClient(
        {
            "host": "192.0.2.1",
            "port": 52000,
            "encryption_key": "11" * 32,
            "command_username": "user",
            "command_password": "pass",
        }
    )
    client._send_wire = AsyncMock()
    acked: list[int] = []
    client._build_clone_ack = MagicMock(
        side_effect=lambda message, _id: (
            acked.append(int.from_bytes(message["data_header"][0:4], "big")) or b"ack"
        )
    )
    reply = b"<FLEXML_REPLY>" + b"x" * (25000 - len(b"<FLEXML_REPLY></FLEXML_REPLY>"))
    reply += b"</FLEXML_REPLY>"
    assert len(reply) == 25000
    pending = asyncio.get_running_loop().create_future()
    client._pending_reply = pending

    parts = [reply[0:10240], reply[10240:20480], reply[20480:]]
    for index, part in enumerate(parts):
        length = 25000 if index == 0 else REPLY_CHUNK_LENGTH
        await client._handle_message(
            {
                "message_id": MSG_DATA,
                "rct_sequence": index,
                "new_application_message": index == 0,
                "application_length": length,
                "data_header": length.to_bytes(4, "big") + b"\x01\x00\x00\x00",
                "app_data": part,
            }
        )

    assert acked == [10240, 20480, 25000]
    assert pending.result() == reply.decode()


def _client():
    from unittest.mock import AsyncMock, MagicMock

    from custom_components.spc_flexc.flexc.connection import FlexCClient

    client = FlexCClient(
        {
            "host": "192.0.2.1",
            "port": 52000,
            "encryption_key": "11" * 32,
            "command_username": "user",
            "command_password": "pass",
        }
    )
    client._send_wire = AsyncMock()
    acked: list[int] = []
    client._build_clone_ack = MagicMock(
        side_effect=lambda message, _id: (
            acked.append(int.from_bytes(message["data_header"][0:4], "big")) or b"ack"
        )
    )
    return client, acked


def _data(seq: int, data: bytes, *, start: bool, total: int = 25000) -> dict:
    from custom_components.spc_flexc.flexc.connection import MSG_DATA

    length = total if start else REPLY_CHUNK_LENGTH
    return {
        "message_id": MSG_DATA,
        "spt_sequence": seq,
        "rct_sequence": seq,
        "new_application_message": start,
        "application_length": length,
        "data_header": length.to_bytes(4, "big") + b"\x01\x00\x00\x00",
        "app_data": data,
    }


def _reply(length: int) -> bytes:
    body = b"x" * (length - len(b"<FLEXML_REPLY></FLEXML_REPLY>"))
    return b"<FLEXML_REPLY>" + body + b"</FLEXML_REPLY>"


async def test_repeated_part_is_not_appended_twice() -> None:
    import asyncio

    client, acked = _client()
    reply = _reply(25000)
    pending = asyncio.get_running_loop().create_future()
    client._pending_reply = pending

    first = _data(1, reply[0:10240], start=True)
    second = _data(2, reply[10240:20480], start=False)
    for message in (first, second, second, _data(3, reply[20480:], start=False)):
        await client._handle_message(message)

    assert acked == [10240, 20480, 20480, 25000]
    assert pending.result() == reply.decode()


async def test_interrupted_reply_does_not_leak_into_a_new_session() -> None:
    """A multi-part reply cut off by a new SPC connection starts from nothing.

    After the replacement a continuation without the new-message marker is
    acknowledged with one part length, not the old session's count, and is
    not appended. The next reply on the new session is counted from zero.
    """
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from custom_components.spc_flexc.flexc.connection import FlexCConnectionError

    client, acked = _client()
    old_writer = MagicMock()
    client._writer = old_writer
    old_reply = asyncio.get_running_loop().create_future()
    client._pending_reply = old_reply
    reply = _reply(25000)
    await client._handle_message(_data(1, reply[0:10240], start=True))
    await client._handle_message(_data(2, reply[10240:20480], start=False))
    assert client._ack_received == 20480

    # The SPC opens a new connection; it closes straight away in this test.
    reader = MagicMock()
    reader.readexactly = AsyncMock(side_effect=asyncio.IncompleteReadError(b"", 16))
    writer = MagicMock()
    writer.get_extra_info.return_value = ("192.0.2.1", 12345)
    writer.wait_closed = AsyncMock()
    await client._handle_client(reader, writer)

    assert isinstance(old_reply.exception(), FlexCConnectionError)
    assert client._ack_total is None
    assert client._ack_received == 0
    assert client._response_length is None
    assert client._response_buffer == bytearray()

    # A stray continuation of the old reply on the new session.
    new_reply = asyncio.get_running_loop().create_future()
    client._pending_reply = new_reply
    await client._handle_message(_data(3, reply[20480:], start=False))
    assert acked[-1] == REPLY_CHUNK_LENGTH
    assert client._response_buffer == bytearray()
    assert not new_reply.done()

    # The next reply is counted from zero.
    fresh = _reply(12000)
    await client._handle_message(_data(10, fresh[0:10240], start=True, total=12000))
    await client._handle_message(_data(11, fresh[10240:], start=False, total=12000))
    assert acked[-2:] == [10240, 12000]
    assert new_reply.result() == fresh.decode()


def test_reset_reply_state_clears_ack_tracking() -> None:
    """Command start and cleanup use the same reset as a new session."""
    client, _ = _client()
    client._ack_total = 25000
    client._ack_received = 20480
    client._ack_last_part = (2, b"b")
    client._response_buffer = bytearray(b"partial")
    client._response_length = 25000
    client._reset_reply_state()
    assert client._ack_total is None
    assert client._ack_received == 0
    assert client._ack_last_part is None
    assert client._response_buffer == bytearray()
    assert client._response_length is None
