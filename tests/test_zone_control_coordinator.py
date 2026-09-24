"""Tests for SPC FlexC zone-control coordinator behavior."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.spc_flexc.flexc.connection import FlexCCommandTimeout
from custom_components.spc_flexc.models import DoorState, SpcState, ZoneState
from custom_components.spc_flexc.zone_control_coordinator import (
    SpcFlexCZoneControlCoordinator,
    _bool_or_none,
    _door_state_from_status,
    _int_or_none,
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
@pytest.mark.parametrize(
    ("method", "zone", "message"),
    [
        ("async_set_zone_inhibited", ZoneState(zone_id=1), "allow inhibition"),
        (
            "async_set_zone_inhibited",
            ZoneState(zone_id=1, raw={"INHIBITED": "1"}),
            None,
        ),
        ("async_set_zone_isolated", ZoneState(zone_id=1), "allow isolation"),
        (
            "async_set_zone_isolated",
            ZoneState(zone_id=1, raw={"ISOLATED": "1"}),
            None,
        ),
    ],
)
async def test_zone_control_permission_and_noop(method, zone, message) -> None:
    coordinator = _coordinator_with_zone(zone)
    call = getattr(SpcFlexCZoneControlCoordinator, method)
    if message is None:
        await call(coordinator, 1, True)
        coordinator.client.async_ensure_connected.assert_not_awaited()
    else:
        with pytest.raises(ValueError, match=message):
            await call(coordinator, 1, True)


@pytest.mark.asyncio
async def test_zone_control_unknown_zone_and_deactivation_permissions() -> None:
    coordinator = _coordinator_with_zone(ZoneState(zone_id=1))
    coordinator.state.zones.clear()
    with pytest.raises(ValueError, match="Unknown SPC zone"):
        await SpcFlexCZoneControlCoordinator.async_set_zone_inhibited(
            coordinator, 1, True
        )
    with pytest.raises(ValueError, match="Unknown SPC zone"):
        await SpcFlexCZoneControlCoordinator.async_set_zone_isolated(
            coordinator, 1, True
        )

    coordinator = _coordinator_with_zone(
        ZoneState(zone_id=1, raw={"INHIBITED": "1", "ISOLATED": "1"})
    )
    with pytest.raises(ValueError, match="de-inhibition"):
        await SpcFlexCZoneControlCoordinator.async_set_zone_inhibited(
            coordinator, 1, False
        )
    with pytest.raises(ValueError, match="de-isolation"):
        await SpcFlexCZoneControlCoordinator.async_set_zone_isolated(
            coordinator, 1, False
        )


@pytest.mark.asyncio
async def test_zone_control_wrapper_methods() -> None:
    coordinator = MagicMock(spec=SpcFlexCZoneControlCoordinator)
    coordinator.async_set_zone_inhibited = AsyncMock()
    coordinator.async_set_zone_isolated = AsyncMock()
    await SpcFlexCZoneControlCoordinator.async_inhibit_zone(coordinator, 1)
    await SpcFlexCZoneControlCoordinator.async_deinhibit_zone(coordinator, 1)
    await SpcFlexCZoneControlCoordinator.async_isolate_zone(coordinator, 1)
    await SpcFlexCZoneControlCoordinator.async_deisolate_zone(coordinator, 1)
    coordinator.async_set_zone_inhibited.assert_any_await(1, True)
    coordinator.async_set_zone_inhibited.assert_any_await(1, False)
    coordinator.async_set_zone_isolated.assert_any_await(1, True)
    coordinator.async_set_zone_isolated.assert_any_await(1, False)


@pytest.mark.asyncio
async def test_refresh_zone_retries_and_validates_returned_id() -> None:
    coordinator = _coordinator_with_zone(ZoneState(zone_id=1))
    coordinator.client.async_get_zone_status = AsyncMock(
        side_effect=[[], [_zone_status(INHIBITED="1")]]
    )
    with patch(
        "custom_components.spc_flexc.zone_control_coordinator.asyncio.sleep",
        new=AsyncMock(),
    ):
        await SpcFlexCZoneControlCoordinator._async_refresh_zone_after_control(
            coordinator, 1, expected_attribute="inhibited", expected_state=True
        )
    assert coordinator.client.async_get_zone_status.await_count == 2
    coordinator.async_set_updated_data.assert_called_once_with(coordinator.state)

    coordinator.client.async_get_zone_status = AsyncMock(
        return_value=[{"ZONE_ID": "2"}]
    )
    with pytest.raises(ValueError, match="returned zone 2"):
        await SpcFlexCZoneControlCoordinator._async_refresh_zone_after_control(
            coordinator, 1, expected_attribute="inhibited", expected_state=True
        )


@pytest.mark.asyncio
async def test_refresh_zone_fails_without_confirmation() -> None:
    coordinator = _coordinator_with_zone(ZoneState(zone_id=1))
    coordinator.client.async_get_zone_status = AsyncMock(return_value=[_zone_status()])
    with (
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.asyncio.sleep",
            new=AsyncMock(),
        ),
        pytest.raises(ValueError, match="did not confirm"),
    ):
        await SpcFlexCZoneControlCoordinator._async_refresh_zone_after_control(
            coordinator, 1, expected_attribute="inhibited", expected_state=True
        )
    assert coordinator.client.async_get_zone_status.await_count == 3
    coordinator.async_set_updated_data.assert_called_once_with(coordinator.state)


def test_update_zone_from_control_status() -> None:
    coordinator = _coordinator_with_zone(ZoneState(zone_id=1))
    raw = _zone_status(
        TYPE="2",
        ALARM_STATE="4",
        INHIBIT_ALLOWED="1",
        ISOLATE_ALLOWED="0",
        ACTUATIONS_SINCE_LAST_READ="3",
    )
    SpcFlexCZoneControlCoordinator._update_zone_from_control_status(coordinator, 1, raw)
    zone = coordinator.state.zones[1]
    assert zone.name == "TV"
    assert zone.area_id == 1
    assert zone.zone_type == 2
    assert zone.alarm_state == 4
    assert zone.inhibit_allowed is True
    assert zone.isolate_allowed is False
    assert zone.actuations_since_last_read == 3
    assert zone.raw == raw
    assert zone.updated_at is not None


def test_door_state_and_scalar_helpers() -> None:
    raw = {
        "DOOR_ID": "4",
        "DOOR_NAME": "Entrée",
        "STATUS": "2",
        "DOOR_MODE": "5",
        "DPS_INPUT": "1",
        "DRS_INPUT": "0",
        "READER1_FORMAT": "3",
        "READER2_FORMAT": "bad",
        "ZONE_ID": "7",
        "ZONE_NAME": "Porte",
        "AREA_ID": "1",
        "AREA_NAME": "Logis",
        "AREA_SIDE_1": "2",
        "AREA_SIDE_1_NAME": "Garage",
        "ENTRY_EXIT": "1",
        "NORMAL_ALLOWED": "0",
        "LOCK_ALLOWED": "x",
    }
    door = _door_state_from_status(raw)
    assert isinstance(door, DoorState)
    assert door.door_id == 4
    assert door.name == "Entrée"
    assert door.mode == 5
    assert door.reader2_format is None
    assert door.entry_exit is True
    assert door.normal_allowed is False
    assert door.lock_allowed is None
    assert door.raw == raw
    assert _int_or_none(None) is None
    assert _int_or_none(" 12 ") == 12
    assert _int_or_none("bad") is None
    assert _bool_or_none(None) is None
    assert _bool_or_none("0") is False
    assert _bool_or_none("1") is True
    assert _bool_or_none("2") is None


def test_update_door_states_detects_changes() -> None:
    coordinator = MagicMock(spec=SpcFlexCZoneControlCoordinator)
    coordinator.state = SpcState()
    raw = {"DOOR_ID": "1", "DOOR_NAME": "Garage", "STATUS": "0"}
    assert (
        SpcFlexCZoneControlCoordinator._update_door_states(coordinator, [raw]) is True
    )
    assert (
        SpcFlexCZoneControlCoordinator._update_door_states(coordinator, [raw]) is False
    )
    changed = {**raw, "STATUS": "1"}
    assert (
        SpcFlexCZoneControlCoordinator._update_door_states(coordinator, [changed])
        is True
    )


@pytest.mark.asyncio
async def test_control_door_validation_and_refresh() -> None:
    coordinator = MagicMock(spec=SpcFlexCZoneControlCoordinator)
    coordinator.state = SpcState(doors={1: DoorState(door_id=1, name="Garage")})
    coordinator.client = MagicMock()
    coordinator.client.command_username = "user"
    coordinator.client.command_password = "password"
    coordinator.client.async_ensure_connected = AsyncMock()
    coordinator.client.async_send_flexml = AsyncMock(side_effect=["control", "status"])
    coordinator._client_operation_lock = AsyncMockContextManager()
    coordinator.async_set_updated_data = MagicMock()
    coordinator._update_door_states = lambda raw: (
        SpcFlexCZoneControlCoordinator._update_door_states(coordinator, raw)
    )

    with pytest.raises(ValueError, match="Unknown SPC door"):
        await SpcFlexCZoneControlCoordinator.async_control_door(coordinator, 2, 5)
    with pytest.raises(ValueError, match="Unsupported SPC door action"):
        await SpcFlexCZoneControlCoordinator.async_control_door(coordinator, 1, 1)

    with (
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.build_door_control_command",
            return_value="cmd",
        ),
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.parse_door_control"
        ),
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.build_door_status_batch",
            return_value="status-cmd",
        ),
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.parse_door_status",
            return_value=[{"DOOR_ID": "1", "STATUS": "1"}],
        ),
    ):
        await SpcFlexCZoneControlCoordinator.async_control_door(coordinator, 1, 5)
    coordinator.async_set_updated_data.assert_called_once_with(coordinator.state)


@pytest.mark.asyncio
async def test_control_door_rejects_bad_refresh() -> None:
    coordinator = MagicMock(spec=SpcFlexCZoneControlCoordinator)
    coordinator.state = SpcState(doors={1: DoorState(door_id=1)})
    coordinator.client = MagicMock()
    coordinator.client.command_username = "user"
    coordinator.client.command_password = "password"
    coordinator.client.async_ensure_connected = AsyncMock()
    coordinator.client.async_send_flexml = AsyncMock(side_effect=["control", "status"])
    coordinator._client_operation_lock = AsyncMockContextManager()

    with (
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.build_door_control_command",
            return_value="cmd",
        ),
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.parse_door_control"
        ),
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.build_door_status_batch",
            return_value="status-cmd",
        ),
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.parse_door_status",
            return_value=[],
        ),
        pytest.raises(ValueError, match="returned no status"),
    ):
        await SpcFlexCZoneControlCoordinator.async_control_door(coordinator, 1, 5)

    coordinator.client.async_send_flexml = AsyncMock(side_effect=["control", "status"])
    with (
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.build_door_control_command",
            return_value="cmd",
        ),
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.parse_door_control"
        ),
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.build_door_status_batch",
            return_value="status-cmd",
        ),
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.parse_door_status",
            return_value=[{"DOOR_ID": "2"}],
        ),
        pytest.raises(ValueError, match="returned door 2"),
    ):
        await SpcFlexCZoneControlCoordinator.async_control_door(coordinator, 1, 5)


@pytest.mark.asyncio
async def test_control_door_recovers_session_but_does_not_retry_unknown_effect() -> (
    None
):
    """Door controls recover transport but are never replayed without proven semantics."""
    coordinator = MagicMock(spec=SpcFlexCZoneControlCoordinator)
    coordinator.state = SpcState(doors={1: DoorState(door_id=1, name="Garage")})
    coordinator.client = MagicMock()
    coordinator.client.command_username = "user"
    coordinator.client.command_password = "password"
    coordinator.client.async_ensure_connected = AsyncMock()
    coordinator.client.async_recover_session = AsyncMock()
    coordinator.client.async_send_flexml = AsyncMock(
        side_effect=[FlexCCommandTimeout("timeout"), "status"]
    )
    coordinator._client_operation_lock = AsyncMockContextManager()
    coordinator.async_set_updated_data = MagicMock()
    coordinator._update_door_states = lambda raw: (
        SpcFlexCZoneControlCoordinator._update_door_states(coordinator, raw)
    )

    with (
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.build_door_control_command",
            return_value="control-cmd",
        ),
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.build_door_status_batch",
            return_value="status-cmd",
        ),
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.parse_door_status",
            return_value=[{"DOOR_ID": "1", "STATUS": "1"}],
        ),
    ):
        await SpcFlexCZoneControlCoordinator.async_control_door(coordinator, 1, 8)

    coordinator.client.async_recover_session.assert_awaited_once_with()
    assert coordinator.client.async_send_flexml.await_count == 2
    assert coordinator.client.async_send_flexml.await_args_list[0].args == (
        "control-cmd",
    )
    assert coordinator.client.async_send_flexml.await_args_list[1].args == (
        "status-cmd",
    )
    coordinator.async_set_updated_data.assert_called_once_with(coordinator.state)


@pytest.mark.asyncio
async def test_control_door_recovers_verification_timeout_without_false_failure() -> None:
    """A door status timeout is recovered after an accepted control response."""
    coordinator = MagicMock(spec=SpcFlexCZoneControlCoordinator)
    coordinator.state = SpcState(doors={1: DoorState(door_id=1, name="Garage")})
    coordinator.client = MagicMock()
    coordinator.client.command_username = "user"
    coordinator.client.command_password = "password"
    coordinator.client.async_ensure_connected = AsyncMock()
    coordinator.client.async_recover_session = AsyncMock()
    coordinator.client.async_send_flexml = AsyncMock(
        side_effect=["control", FlexCCommandTimeout("timeout"), "status"]
    )
    coordinator._client_operation_lock = AsyncMockContextManager()
    coordinator.async_set_updated_data = MagicMock()
    coordinator._update_door_states = lambda raw: (
        SpcFlexCZoneControlCoordinator._update_door_states(coordinator, raw)
    )

    with (
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.build_door_control_command",
            return_value="control-cmd",
        ),
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.parse_door_control"
        ),
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.build_door_status_batch",
            return_value="status-cmd",
        ),
        patch(
            "custom_components.spc_flexc.zone_control_coordinator.parse_door_status",
            return_value=[{"DOOR_ID": "1", "STATUS": "1"}],
        ),
    ):
        await SpcFlexCZoneControlCoordinator.async_control_door(coordinator, 1, 8)

    coordinator.client.async_recover_session.assert_awaited_once_with()
    assert coordinator.client.async_send_flexml.await_count == 3
    coordinator.async_set_updated_data.assert_called_once_with(coordinator.state)


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
