"""Protocol-driven SPC FlexC object discovery."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from ..const import DISCOVERY_BATCH_SIZE
from .connection import FlexCClient
from .flexml import (
    FlexMLDiscoveryResult,
    build_area_status_batch,
    build_door_status_batch,
    build_zone_status_batch,
    parse_area_status_discovery,
    parse_door_status_discovery,
    parse_zone_status_discovery,
)

BatchBuilder = Callable[[Iterable[int], str, str], str]
BatchParser = Callable[[str], FlexMLDiscoveryResult]


async def _async_discover_statuses(
    client: FlexCClient,
    *,
    maximum_id: int,
    builder: BatchBuilder,
    parser: BatchParser,
) -> list[dict[str, str]]:
    """Discover configured objects until FlexC reports RESULT=102."""
    statuses: list[dict[str, str]] = []

    for first_id in range(1, maximum_id + 1, DISCOVERY_BATCH_SIZE):
        last_id = min(first_id + DISCOVERY_BATCH_SIZE - 1, maximum_id)
        object_ids = range(first_id, last_id + 1)
        command = builder(
            object_ids,
            client.command_username,
            client.command_password,
        )
        response = await client.async_send_flexml(command)
        result = parser(response)
        statuses.extend(result.statuses)

        if result.boundary_reached:
            break

    return statuses


async def async_discover_areas(
    client: FlexCClient,
    maximum_id: int,
) -> list[dict[str, str]]:
    """Discover configured SPC areas."""
    return await _async_discover_statuses(
        client,
        maximum_id=maximum_id,
        builder=build_area_status_batch,
        parser=parse_area_status_discovery,
    )


async def async_discover_zones(
    client: FlexCClient,
    maximum_id: int,
) -> list[dict[str, str]]:
    """Discover configured SPC zones."""
    return await _async_discover_statuses(
        client,
        maximum_id=maximum_id,
        builder=build_zone_status_batch,
        parser=parse_zone_status_discovery,
    )


async def async_discover_doors(
    client: FlexCClient,
    maximum_id: int,
) -> list[dict[str, str]]:
    """Discover configured SPC access-control doors."""
    return await _async_discover_statuses(
        client,
        maximum_id=maximum_id,
        builder=build_door_status_batch,
        parser=parse_door_status_discovery,
    )
