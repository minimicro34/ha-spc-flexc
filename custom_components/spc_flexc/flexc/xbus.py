"""X-BUS status helpers for the SPC FlexC protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .flexml import build_xbus_status_command, parse_xbus_status

if TYPE_CHECKING:
    from .connection import FlexCClient


async def async_get_xbus_status(client: FlexCClient) -> list[dict[str, str]]:
    """Read the aggregate X-BUS inventory/status from the panel."""
    command = build_xbus_status_command(
        client.command_username,
        client.command_password,
    )
    response = await client.async_send_flexml(command)
    return parse_xbus_status(response)
