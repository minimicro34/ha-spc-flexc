"""Tests for validated FlexC zone-control operations."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.spc_flexc.flexc.zone_control import (
    ZONE_ACTION_DEINHIBIT,
    ZONE_ACTION_DEISOLATE,
    ZONE_ACTION_INHIBIT,
    ZONE_ACTION_ISOLATE,
    async_set_zone_inhibited,
    async_set_zone_isolated,
)
from custom_components.spc_flexc.zone_control_coordinator import (
    SpcFlexCZoneControlCoordinator,
)

ZONE_CONTROL_REPLY = (
    '<FLEXML_REPLY VER="1.0"><REPLY_ZONE_CONTROL RESULT="0" '
    'CMD_RESULT="OK"><ZONE_CONTROL ZONE_ID="1" RESULT="0"/>'
    "</REPLY_ZONE_CONTROL></FLEXML_REPLY>"
)


@pytest.mark.asyncio
async def test_async_set_zone_inhibited_uses_validated_actions() -> None:
    client = MagicMock()
    client.command_username = "HomeAssistant"
    client.command_password = "Password"
    client.async_send_flexml = AsyncMock(
        side_effect=[ZONE_CONTROL_REPLY, ZONE_CONTROL_REPLY]
    )

    await async_set_zone_inhibited(client, 1, True)
    await async_set_zone_inhibited(client, 1, False)

    assert (
        f'ACTION="{ZONE_ACTION_INHIBIT}"'
        in client.async_send_flexml.await_args_list[0].args[0]
    )
    assert (
        f'ACTION="{ZONE_ACTION_DEINHIBIT}"'
        in client.async_send_flexml.await_args_list[1].args[0]
    )


@pytest.mark.asyncio
async def test_async_set_zone_isolated_uses_validated_actions() -> None:
    """Isolation and de-isolation use real-panel validated actions 2 and 3."""
    client = MagicMock()
    client.command_username = "HomeAssistant"
    client.command_password = "Password"
    client.async_send_flexml = AsyncMock(
        side_effect=[ZONE_CONTROL_REPLY, ZONE_CONTROL_REPLY]
    )

    await async_set_zone_isolated(client, 1, True)
    await async_set_zone_isolated(client, 1, False)

    assert (
        f'ACTION="{ZONE_ACTION_ISOLATE}"'
        in client.async_send_flexml.await_args_list[0].args[0]
    )
    assert (
        f'ACTION="{ZONE_ACTION_DEISOLATE}"'
        in client.async_send_flexml.await_args_list[1].args[0]
    )


@pytest.mark.asyncio
async def test_door_polling_restarts_if_task_stops_unexpectedly() -> None:
    coordinator = MagicMock()
    coordinator._discovery_requested = True
    coordinator._schedule_door_polling = MagicMock()
    coordinator._door_poll_task = asyncio.current_task()
    sleep = AsyncMock(side_effect=asyncio.CancelledError())

    with (
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.asyncio.sleep", sleep
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await SpcFlexCZoneControlCoordinator._async_door_poll_loop(coordinator)

    coordinator._schedule_door_polling.assert_called_once_with()
