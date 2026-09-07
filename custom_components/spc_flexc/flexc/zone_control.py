"""Validated FlexC zone-control operations for SPC panels."""

from __future__ import annotations

from .connection import FlexCClient
from .flexml import build_zone_control_command, parse_zone_control

ZONE_ACTION_INHIBIT = 0
ZONE_ACTION_DEINHIBIT = 1


async def async_set_zone_inhibited(
    client: FlexCClient,
    zone_id: int,
    inhibited: bool,
) -> None:
    """Set the validated inhibition state for one SPC zone."""
    action = ZONE_ACTION_INHIBIT if inhibited else ZONE_ACTION_DEINHIBIT
    command = build_zone_control_command(
        zone_id,
        action,
        client.command_username,
        client.command_password,
    )
    response = await client.async_send_flexml(command)
    parse_zone_control(response, zone_id)
