"""Tests for SPC FlexC zone-control coordinator behavior."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.spc_flexc.models import SpcState, ZoneState
from custom_components.spc_flexc.zone_control_coordinator import (
    SpcFlexCZoneControlCoordinator,
)


@pytest.mark.asyncio
async def test_inhibit_zone_refreshes_explicit_inhibition_state() -> None:
    coordinator = _coordinator_with_zone(
        ZoneState(
            zone_id=1,
            inhibit_allowed=True,
            raw={"ZONE_ID": "1", "INHIBIT_ALLOWED": "1"},
        )
    )
    coordinator.client.async_get_zone_status = AsyncMock(
        return_value=[_zone_status(INHIBITED="1", DEINHIBIT_ALLOWED="1")]
    )

    with patch(
        "custom_components.spc_flexc.zone_control_coordinator.async_set_zone_inhibited",
        new=AsyncMock(),
    ):
        await SpcFlexCZoneControlCoordinator.async_set_zone_inhibited(
            coordinator, 1, True
        )

    assert coordinator.state.zones[1].inhibited is True
    assert coordinator.state.zones[1].deinhibit_allowed is True


@pytest.mark.asyncio
async def test_isolate_zone_refreshes_explicit_isolation_state() -> None:
    """A successful isolate must be confirmed by ISOLATED=1."""
    coordinator = _coordinator_with_zone(
        ZoneState(
            zone_id=1,
            isolate_allowed=True,
            raw={"ZONE_ID": "1", "ISOLATE_ALLOWED": "1"},
        )
    )
    coordinator.client.async_get_zone_status = AsyncMock(
        return_value=[_zone_status(ISOLATED="1", DEISOLATE_ALLOWED="1")]
    )

    with patch(
        "custom_components.spc_flexc.zone_control_coordinator.async_set_zone_isolated",
        new=AsyncMock(),
    ):
        await SpcFlexCZoneControlCoordinator.async_set_zone_isolated(
            coordinator, 1, True
        )

    assert coordinator.state.zones[1].isolated is True
    assert coordinator.state.zones[1].deisolate_allowed is True


@pytest.mark.asyncio
async def test_isolate_zone_requires_explicit_permission() -> None:
    """No isolation command is sent without ISOLATE_ALLOWED=1."""
    coordinator = _coordinator_with_zone(
        ZoneState(zone_id=1, isolate_allowed=None, raw={"ZONE_ID": "1"})
    )

    control = AsyncMock()
    with (
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.async_set_zone_isolated",
            new=control,
        ),
        pytest.raises(ValueError, match="does not currently allow isolation"),
    ):
        await SpcFlexCZoneControlCoordinator.async_set_zone_isolated(
            coordinator, 1, True
        )

    control.assert_not_awaited()


def _coordinator_with_zone(zone: ZoneState) -> MagicMock:
    coordinator = MagicMock(spec=SpcFlexCZoneControlCoordinator)
    coordinator.state = SpcState(zones={1: zone})
    coordinator.client = MagicMock()
    coordinator.client.async_ensure_connected = AsyncMock()
    coordinator._client_operation_lock = AsyncMockContextManager()
    coordinator.async_set_updated_data = MagicMock()
    coordinator._update_zone_from_control_status = lambda zone_id, raw: (
        SpcFlexCZoneControlCoordinator._update_zone_from_control_status(
            coordinator, zone_id, raw
        )
    )
    coordinator._async_refresh_zone_after_control = lambda zone_id, **kwargs: (
        SpcFlexCZoneControlCoordinator._async_refresh_zone_after_control(
            coordinator, zone_id, **kwargs
        )
    )
    return coordinator


def _zone_status(**extra: str) -> dict[str, str]:
    status = {
        "ZONE_ID": "1",
        "ZONE_NAME": "TV",
        "AREA_ID": "1",
        "AREA_NAME": "Logis",
        "STATUS": "0",
        "INPUT": "0",
        "LOGIC_INPUT": "0",
        "PROC_STATE": "0",
    }
    status.update(extra)
    return status


class AsyncMockContextManager:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None
