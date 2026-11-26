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


def test_data_ack_length_counts_parts_up_to_total() -> None:
    from unittest.mock import MagicMock

    from custom_components.spc_flexc.flexc.connection import FlexCClient

    client = MagicMock(spec=FlexCClient)
    client._ack_total = None
    client._ack_received = 0
    first = {
        "application_length": 25000,
        "new_application_message": True,
        "app_data": b"x" * REPLY_CHUNK_LENGTH,
    }
    middle = {
        "application_length": REPLY_CHUNK_LENGTH,
        "new_application_message": False,
        "app_data": b"x" * REPLY_CHUNK_LENGTH,
    }
    lengths = [
        FlexCClient._data_ack_length(client, part) for part in (first, middle, middle)
    ]
    assert lengths == [10240, 20480, 25000]
    # A new message starts counting again.
    assert (
        FlexCClient._data_ack_length(
            client, {**first, "application_length": 500, "app_data": b"x" * 512}
        )
        == 500
    )


def test_data_ack_length_unknown_without_start() -> None:
    from unittest.mock import MagicMock

    from custom_components.spc_flexc.flexc.connection import FlexCClient

    client = MagicMock(spec=FlexCClient)
    client._ack_total = None
    client._ack_received = 0
    part = {
        "application_length": 10240,
        "new_application_message": False,
        "app_data": b"",
    }
    assert FlexCClient._data_ack_length(client, part) is None


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
