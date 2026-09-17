"""Tests for SPC FlexC X-BUS helpers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.spc_flexc.flexc.xbus import async_get_xbus_status


@pytest.mark.asyncio
async def test_get_xbus_status_builds_command_and_parses_reply() -> None:
    client = MagicMock()
    client.command_username = "user"
    client.command_password = "password"
    client.async_send_flexml = AsyncMock(
        return_value=(
            '<FLEXML_REPLY VER="1.0">'
            '<REPLY_STATUS_XBUS RESULT="0" CMD_RESULT="OK">'
            '<ENETNODE ID="7" NAME="SPCE650" TYPE="2" ICOUNT="8" OCOUNT="2" />'
            "</REPLY_STATUS_XBUS>"
            "</FLEXML_REPLY>"
        )
    )

    result = await async_get_xbus_status(client)

    assert result == [
        {"ID": "7", "NAME": "SPCE650", "TYPE": "2", "ICOUNT": "8", "OCOUNT": "2"}
    ]
    command = client.async_send_flexml.await_args.args[0]
    assert "<CMD_STATUS_XBUS />" in command
    assert 'PANEL_USERNAME="user"' in command
