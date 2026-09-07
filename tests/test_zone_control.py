"""Tests for validated FlexC zone-control operations."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.spc_flexc.flexc.zone_control import (
    ZONE_ACTION_DEINHIBIT,
    ZONE_ACTION_INHIBIT,
    async_set_zone_inhibited,
)


@pytest.mark.asyncio
async def test_async_set_zone_inhibited_uses_validated_actions() -> None:
    """Inhibit and de-inhibit must use the validated action values 0 and 1."""
    client = MagicMock()
    client.command_username = "HomeAssistant"
    client.command_password = "Password"
    client.async_send_flexml = AsyncMock(
        side_effect=[
            '<FLEXML_REPLY VER="1.0"><REPLY_ZONE_CONTROL RESULT="0" '
            'CMD_RESULT="OK"><ZONE_CONTROL ZONE_ID="1" RESULT="0"/>'
            '</REPLY_ZONE_CONTROL></FLEXML_REPLY>',
            '<FLEXML_REPLY VER="1.0"><REPLY_ZONE_CONTROL RESULT="0" '
            'CMD_RESULT="OK"><ZONE_CONTROL ZONE_ID="1" RESULT="0"/>'
            '</REPLY_ZONE_CONTROL></FLEXML_REPLY>',
        ]
    )

    await async_set_zone_inhibited(client, 1, True)
    await async_set_zone_inhibited(client, 1, False)

    first_command = client.async_send_flexml.await_args_list[0].args[0]
    second_command = client.async_send_flexml.await_args_list[1].args[0]

    assert f'ACTION="{ZONE_ACTION_INHIBIT}"' in first_command
    assert f'ACTION="{ZONE_ACTION_DEINHIBIT}"' in second_command
