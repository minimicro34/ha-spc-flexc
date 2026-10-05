"""Tests for validated SPC zone restoration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.spc_flexc.models import SpcState, ZoneState
from custom_components.spc_flexc.zone_control_coordinator import (
    SpcFlexCZoneControlCoordinator,
)


class AsyncMockContextManager:
    """Minimal async lock context for coordinator unit tests."""

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


def _coordinator(zone: ZoneState) -> MagicMock:
    coordinator = MagicMock(spec=SpcFlexCZoneControlCoordinator)
    coordinator.state = SpcState(zones={zone.zone_id: zone})
    coordinator.client = MagicMock()
    coordinator.client.async_ensure_connected = AsyncMock()
    coordinator.client.async_get_zone_status = AsyncMock()
    coordinator._client_operation_lock = AsyncMockContextManager()
    coordinator.async_set_updated_data = MagicMock()
    coordinator._update_zone_from_control_status = lambda zone_id, raw: (
        SpcFlexCZoneControlCoordinator._update_zone_from_control_status(
            coordinator, zone_id, raw
        )
    )
    return coordinator


@pytest.mark.asyncio
async def test_restore_zone_rejects_unknown_zone() -> None:
    coordinator = _coordinator(ZoneState(zone_id=1, restore_allowed=True))

    with pytest.raises(ValueError, match="Unknown SPC zone 2"):
        await SpcFlexCZoneControlCoordinator.async_restore_zone(coordinator, 2)

    coordinator.client.async_ensure_connected.assert_not_awaited()


@pytest.mark.asyncio
async def test_restore_zone_requires_explicit_permission() -> None:
    coordinator = _coordinator(ZoneState(zone_id=1, restore_allowed=False))

    with pytest.raises(ValueError, match="does not currently allow restoration"):
        await SpcFlexCZoneControlCoordinator.async_restore_zone(coordinator, 1)

    coordinator.client.async_ensure_connected.assert_not_awaited()


@pytest.mark.asyncio
async def test_restore_zone_action4_and_verify_permission_clears() -> None:
    coordinator = _coordinator(
        ZoneState(
            zone_id=1,
            name="TV",
            alarm_state=4,
            restore_allowed=True,
            raw={"ZONE_ID": "1", "RESTORE_ALLOWED": "1", "ALARM_STATE": "4"},
        )
    )
    coordinator.client.async_get_zone_status.return_value = [
        {
            "ZONE_ID": "1",
            "ZONE_NAME": "TV",
            "STATUS": "0",
            "INPUT": "0",
            "PROC_STATE": "0",
            "ALARM_STATE": "0",
        }
    ]

    restore = AsyncMock()
    with patch(
        "custom_components.spc_flexc.zone_control_coordinator.async_restore_zone",
        new=restore,
    ):
        await SpcFlexCZoneControlCoordinator.async_restore_zone(coordinator, 1)

    restore.assert_awaited_once_with(coordinator.client, 1)
    coordinator.client.async_get_zone_status.assert_awaited_once_with([1])
    assert coordinator.state.zones[1].restore_allowed is None
    assert coordinator.state.zones[1].alarm_state == 0
    coordinator.async_set_updated_data.assert_called_once_with(coordinator.state)


@pytest.mark.asyncio
async def test_restore_zone_fails_if_panel_still_allows_restore() -> None:
    coordinator = _coordinator(ZoneState(zone_id=1, restore_allowed=True))
    coordinator.client.async_get_zone_status.return_value = [
        {"ZONE_ID": "1", "RESTORE_ALLOWED": "1"}
    ]

    with (
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.async_restore_zone",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.asyncio.sleep",
            new=AsyncMock(),
        ),
        pytest.raises(ValueError, match="still allows restoration"),
    ):
        await SpcFlexCZoneControlCoordinator.async_restore_zone(coordinator, 1)

    assert coordinator.client.async_get_zone_status.await_count == 3
