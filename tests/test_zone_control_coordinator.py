"""Tests for SPC FlexC zone-control coordinator behavior."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.spc_flexc.models import SpcState, ZoneState
from custom_components.spc_flexc.zone_control_coordinator import (
    SpcFlexCZoneControlCoordinator,
)


@pytest.mark.asyncio
async def test_inhibit_zone_refreshes_explicit_inhibition_state() -> None:
    """A successful inhibit must refresh and publish INHIBITED=1."""
    coordinator = MagicMock(spec=SpcFlexCZoneControlCoordinator)
    coordinator.state = SpcState(
        zones={
            1: ZoneState(
                zone_id=1,
                inhibit_allowed=True,
                raw={"ZONE_ID": "1", "INHIBIT_ALLOWED": "1"},
            )
        }
    )
    coordinator.client = MagicMock()
    coordinator.client.async_ensure_connected = AsyncMock()
    coordinator.client.async_get_zone_status = AsyncMock(
        return_value=[
            {
                "ZONE_ID": "1",
                "ZONE_NAME": "TV",
                "AREA_ID": "1",
                "AREA_NAME": "Logis",
                "STATUS": "1",
                "INHIBITED": "1",
                "DEINHIBIT_ALLOWED": "1",
                "ISOLATE_ALLOWED": "1",
                "INPUT": "0",
                "LOGIC_INPUT": "0",
                "PROC_STATE": "0",
            }
        ]
    )
    coordinator._client_operation_lock = AsyncMockContextManager()

    import custom_components.spc_flexc.zone_control_coordinator as module

    original = module.async_set_zone_inhibited
    module.async_set_zone_inhibited = AsyncMock()
    try:
        await SpcFlexCZoneControlCoordinator.async_set_zone_inhibited(
            coordinator, 1, True
        )
    finally:
        module.async_set_zone_inhibited = original

    assert coordinator.state.zones[1].inhibited is True
    assert coordinator.state.zones[1].deinhibit_allowed is True
    coordinator.async_set_updated_data.assert_called_once_with(coordinator.state)


class AsyncMockContextManager:
    """Minimal async context manager for coordinator lock tests."""

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None
