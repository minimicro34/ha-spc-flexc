"""Tests for protocol-driven SPC object discovery."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.spc_flexc.flexc.discovery import async_discover_zones


@pytest.mark.asyncio
async def test_zone_discovery_keeps_holes_and_stops_at_102() -> None:
    """Discovery must continue across empty OK replies and stop at RESULT=102."""
    first_reply = (
        '<FLEXML_REPLY VER="1.0">'
        '<REPLY_GET_ZONE_STATUS RESULT="0" CMD_RESULT="OK">'
        '<ZONE_STATUS ZONE_ID="1" ZONE_NAME="Front" />'
        "</REPLY_GET_ZONE_STATUS>"
        '<REPLY_GET_ZONE_STATUS RESULT="0" CMD_RESULT="OK" />'
        '<REPLY_GET_ZONE_STATUS RESULT="0" CMD_RESULT="OK">'
        '<ZONE_STATUS ZONE_ID="3" ZONE_NAME="Back" />'
        "</REPLY_GET_ZONE_STATUS>"
        "</FLEXML_REPLY>"
    )
    boundary_reply = (
        '<FLEXML_REPLY VER="1.0">'
        '<REPLY_GET_ZONE_STATUS RESULT="102" CMD_RESULT="ERROR" />'
        "</FLEXML_REPLY>"
    )

    client = SimpleNamespace(
        command_username="HomeAssistant",
        command_password="secret",
        async_send_flexml=AsyncMock(side_effect=[first_reply, boundary_reply]),
    )

    statuses = await async_discover_zones(client, 64)

    assert [status["ZONE_ID"] for status in statuses] == ["1", "3"]
    assert client.async_send_flexml.await_count == 2

    first_command = client.async_send_flexml.await_args_list[0].args[0]
    second_command = client.async_send_flexml.await_args_list[1].args[0]
    assert 'ZONE_ID="1"' in first_command
    assert 'ZONE_ID="8"' in first_command
    assert 'ZONE_ID="9"' in second_command
    assert 'ZONE_ID="16"' in second_command
