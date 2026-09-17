"""Tests for SPC Mapping Gate support."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.spc_flexc.flexc.connection import FlexCError
from custom_components.spc_flexc.flexc.flexml import (
    FlexMLError,
    FlexMLReplyError,
    build_mg_control_command,
    build_mg_status_command,
    parse_mg_control,
    parse_mg_status,
)
from custom_components.spc_flexc.mapping_gate_coordinator import (
    SpcFlexCMappingGateCoordinator,
)
from custom_components.spc_flexc.models import MappingGateState, SpcState


class _AsyncLock:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


def test_mg_discovery_uses_aggregate_id_zero() -> None:
    """Mapping Gate discovery must not scan a model-dependent ID range."""
    xml = build_mg_status_command("HomeAssistant", "MyPassword")
    assert '<CMD_GET_MG_STATUS MG_ID="0" />' in xml


def test_parse_mg_status_multiple_mapping_gates() -> None:
    """Aggregate status returns every configured Mapping Gate."""
    response = (
        '<FLEXML_REPLY VER="1.0">'
        '<REPLY_GET_MG_STATUS RESULT="0" CMD_RESULT="OK">'
        '<MG_STATUS MG_ID="1" MG_NAME="Test one" STATE="0" />'
        '<MG_STATUS MG_ID="4" MG_NAME="Test four" STATE="1" />'
        "</REPLY_GET_MG_STATUS></FLEXML_REPLY>"
    )
    assert parse_mg_status(response) == [
        {"MG_ID": "1", "MG_NAME": "Test one", "STATE": "0"},
        {"MG_ID": "4", "MG_NAME": "Test four", "STATE": "1"},
    ]


def test_parse_empty_mg_status() -> None:
    """Panels with no configured Mapping Gate return an empty successful reply."""
    response = (
        '<FLEXML_REPLY VER="1.0">'
        '<REPLY_GET_MG_STATUS RESULT="0" CMD_RESULT="OK">'
        "</REPLY_GET_MG_STATUS></FLEXML_REPLY>"
    )
    assert parse_mg_status(response) == []


def test_mg_control_uses_validated_numeric_actions() -> None:
    """Only the real-panel validated 0/1 actions may be emitted."""
    assert '<CMD_MG_CONTROL MG_ID="1" ACTION="1" />' in build_mg_control_command(
        1, 1, "HomeAssistant", "MyPassword"
    )
    assert '<CMD_MG_CONTROL MG_ID="1" ACTION="0" />' in build_mg_control_command(
        1, 0, "HomeAssistant", "MyPassword"
    )
    with pytest.raises(ValueError):
        build_mg_control_command(1, 2, "HomeAssistant", "MyPassword")


def test_parse_mg_control_real_panel_reply() -> None:
    """Accept the successful reply captured from a real SPC4300."""
    response = (
        '<FLEXML_REPLY VER="1.0">'
        '<REPLY_MG_CONTROL RESULT="0" CMD_RESULT="OK">'
        '<MG_CONTROL MG_ID="1" RESULT="0"/>'
        "</REPLY_MG_CONTROL></FLEXML_REPLY>"
    )
    parse_mg_control(response, 1)


def test_parse_mg_control_rejects_wrong_id() -> None:
    """A successful result for another Mapping Gate must not validate control."""
    response = (
        '<FLEXML_REPLY VER="1.0">'
        '<REPLY_MG_CONTROL RESULT="0" CMD_RESULT="OK">'
        '<MG_CONTROL MG_ID="2" RESULT="0"/>'
        "</REPLY_MG_CONTROL></FLEXML_REPLY>"
    )
    with pytest.raises(FlexMLError):
        parse_mg_control(response, 1)


def test_parse_mg_control_rejects_inner_error() -> None:
    """Reject a failed MG_CONTROL result."""
    response = (
        '<FLEXML_REPLY VER="1.0">'
        '<REPLY_MG_CONTROL RESULT="0" CMD_RESULT="OK">'
        '<MG_CONTROL MG_ID="1" RESULT="54"/>'
        "</REPLY_MG_CONTROL></FLEXML_REPLY>"
    )
    with pytest.raises(FlexMLReplyError):
        parse_mg_control(response, 1)


def test_update_mapping_gate_states_tracks_changes_and_removals() -> None:
    """Mapping Gate snapshots update values, preserve unknown states and remove stale IDs."""
    coordinator = MagicMock()
    coordinator.state = SpcState()
    coordinator.state.mapping_gates[9] = MappingGateState(
        mg_id=9, raw={"MG_ID": "9", "STATE": "1"}
    )

    changed = SpcFlexCMappingGateCoordinator._update_mapping_gate_states(
        coordinator,
        [
            {"MG_ID": "1", "MG_NAME": "One", "STATE": "1"},
            {"MG_ID": "2", "NAME": "Two", "STATE": "2"},
        ],
    )

    assert changed is True
    assert set(coordinator.state.mapping_gates) == {1, 2}
    assert coordinator.state.mapping_gates[1].name == "One"
    assert coordinator.state.mapping_gates[1].state is True
    assert coordinator.state.mapping_gates[2].name == "Two"
    assert coordinator.state.mapping_gates[2].state is None

    changed = SpcFlexCMappingGateCoordinator._update_mapping_gate_states(
        coordinator,
        [
            {"MG_ID": "1", "MG_NAME": "One", "STATE": "1"},
            {"MG_ID": "2", "NAME": "Two", "STATE": "2"},
        ],
    )
    assert changed is False


@pytest.mark.asyncio
async def test_read_mapping_gates_uses_client_credentials() -> None:
    """Aggregate Mapping Gate reads use the authenticated FlexC command channel."""
    coordinator = MagicMock()
    coordinator._client_operation_lock = _AsyncLock()
    coordinator.client.command_username = "HomeAssistant"
    coordinator.client.command_password = "MyPassword"
    coordinator.client.async_ensure_connected = AsyncMock()
    coordinator.client.async_send_flexml = AsyncMock(
        return_value=(
            '<FLEXML_REPLY VER="1.0"><REPLY_GET_MG_STATUS RESULT="0" '
            'CMD_RESULT="OK"><MG_STATUS MG_ID="1" STATE="1" />'
            "</REPLY_GET_MG_STATUS></FLEXML_REPLY>"
        )
    )

    result = await SpcFlexCMappingGateCoordinator._async_read_mapping_gates(coordinator)

    assert result == [{"MG_ID": "1", "STATE": "1"}]
    coordinator.client.async_ensure_connected.assert_awaited_once_with()
    sent = coordinator.client.async_send_flexml.await_args.args[0]
    assert '<CMD_GET_MG_STATUS MG_ID="0" />' in sent


@pytest.mark.asyncio
async def test_discovery_updates_mapping_gates_and_starts_polling() -> None:
    """Successful Mapping Gate discovery publishes state and starts live polling."""
    coordinator = MagicMock()
    coordinator.state = SpcState()
    coordinator._async_read_mapping_gates = AsyncMock(
        return_value=[{"MG_ID": "1", "MG_NAME": "Gate", "STATE": "0"}]
    )
    coordinator._update_mapping_gate_states = MagicMock()
    coordinator._schedule_mg_polling = MagicMock()
    coordinator.async_set_updated_data = MagicMock()

    with patch(
        "custom_components.spc_flexc.zone_control_coordinator.SpcFlexCZoneControlCoordinator._async_discover_panel_objects",
        new=AsyncMock(),
    ):
        await SpcFlexCMappingGateCoordinator._async_discover_panel_objects(coordinator)

    coordinator._update_mapping_gate_states.assert_called_once()
    assert coordinator._mg_discovery_complete is True
    coordinator.async_set_updated_data.assert_called_once_with(coordinator.state)
    coordinator._schedule_mg_polling.assert_called_once_with()


@pytest.mark.asyncio
async def test_discovery_tolerates_mapping_gate_read_failure() -> None:
    """Mapping Gate discovery failure leaves the rest of panel discovery usable."""
    coordinator = MagicMock()
    coordinator._async_read_mapping_gates = AsyncMock(side_effect=FlexCError("offline"))
    coordinator._update_mapping_gate_states = MagicMock()

    with patch(
        "custom_components.spc_flexc.zone_control_coordinator.SpcFlexCZoneControlCoordinator._async_discover_panel_objects",
        new=AsyncMock(),
    ):
        await SpcFlexCMappingGateCoordinator._async_discover_panel_objects(coordinator)

    coordinator._update_mapping_gate_states.assert_not_called()


def test_schedule_mg_polling_requires_discovery_and_single_task() -> None:
    """Mapping Gate polling starts once and only after discovery."""
    coordinator = MagicMock()
    coordinator._mg_discovery_complete = False
    coordinator._mg_poll_task = None
    coordinator.entry.async_create_background_task = MagicMock(return_value="task")

    SpcFlexCMappingGateCoordinator._schedule_mg_polling(coordinator)
    coordinator.entry.async_create_background_task.assert_not_called()

    coordinator._mg_discovery_complete = True
    SpcFlexCMappingGateCoordinator._schedule_mg_polling(coordinator)
    assert coordinator._mg_poll_task == "task"
    coordinator.entry.async_create_background_task.assert_called_once()

    running = MagicMock()
    running.done.return_value = False
    coordinator._mg_poll_task = running
    coordinator.entry.async_create_background_task.reset_mock()
    SpcFlexCMappingGateCoordinator._schedule_mg_polling(coordinator)
    coordinator.entry.async_create_background_task.assert_not_called()


@pytest.mark.asyncio
async def test_mg_polling_updates_only_when_state_changes() -> None:
    """Live polling publishes only changed Mapping Gate snapshots."""
    coordinator = MagicMock()
    coordinator._discovery_requested = False
    coordinator._mg_poll_task = asyncio.current_task()
    coordinator._async_read_mapping_gates = AsyncMock(side_effect=[[{"MG_ID": "1"}], []])
    coordinator._update_mapping_gate_states = MagicMock(side_effect=[False, True])
    coordinator.async_set_updated_data = MagicMock()
    sleep = AsyncMock(side_effect=[None, None, asyncio.CancelledError()])

    with (
        patch(
            "custom_components.spc_flexc.mapping_gate_coordinator.asyncio.sleep", sleep
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await SpcFlexCMappingGateCoordinator._async_mg_poll_loop(coordinator)

    coordinator.async_set_updated_data.assert_called_once_with(coordinator.state)
    assert coordinator._mg_poll_task is None


@pytest.mark.asyncio
async def test_mg_polling_continues_after_expected_error() -> None:
    """A FlexC read failure cannot permanently stop Mapping Gate polling."""
    coordinator = MagicMock()
    coordinator._discovery_requested = False
    coordinator._mg_poll_task = asyncio.current_task()
    coordinator._async_read_mapping_gates = AsyncMock(
        side_effect=[FlexMLError("bad reply"), []]
    )
    coordinator._update_mapping_gate_states = MagicMock(return_value=False)
    sleep = AsyncMock(side_effect=[None, None, asyncio.CancelledError()])

    with (
        patch(
            "custom_components.spc_flexc.mapping_gate_coordinator.asyncio.sleep", sleep
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await SpcFlexCMappingGateCoordinator._async_mg_poll_loop(coordinator)

    assert coordinator._async_read_mapping_gates.await_count == 2


@pytest.mark.asyncio
async def test_mg_polling_restarts_if_task_stops_unexpectedly() -> None:
    """Test an unexpectedly stopped Mapping Gate task schedules a replacement."""
    coordinator = MagicMock()
    coordinator._discovery_requested = True
    coordinator._schedule_mg_polling = MagicMock()
    coordinator._mg_poll_task = asyncio.current_task()
    sleep = AsyncMock(side_effect=asyncio.CancelledError())

    with (
        patch(
            "custom_components.spc_flexc.mapping_gate_coordinator.asyncio.sleep",
            sleep,
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await SpcFlexCMappingGateCoordinator._async_mg_poll_loop(coordinator)

    coordinator._schedule_mg_polling.assert_called_once_with()


@pytest.mark.asyncio
async def test_set_mapping_gate_validates_refresh() -> None:
    """Mapping Gate control publishes only a state confirmed by a fresh panel read."""
    coordinator = MagicMock()
    coordinator.state = SpcState()
    coordinator.state.mapping_gates[1] = MappingGateState(mg_id=1, state=False)
    coordinator._client_operation_lock = _AsyncLock()
    coordinator.client.command_username = "HomeAssistant"
    coordinator.client.command_password = "MyPassword"
    coordinator.client.async_ensure_connected = AsyncMock()
    coordinator.client.async_send_flexml = AsyncMock(
        side_effect=[
            (
                '<FLEXML_REPLY VER="1.0"><REPLY_MG_CONTROL RESULT="0" '
                'CMD_RESULT="OK"><MG_CONTROL MG_ID="1" RESULT="0" />'
                "</REPLY_MG_CONTROL></FLEXML_REPLY>"
            ),
            (
                '<FLEXML_REPLY VER="1.0"><REPLY_GET_MG_STATUS RESULT="0" '
                'CMD_RESULT="OK"><MG_STATUS MG_ID="1" STATE="1" />'
                "</REPLY_GET_MG_STATUS></FLEXML_REPLY>"
            ),
        ]
    )
    coordinator.async_set_updated_data = MagicMock()

    await SpcFlexCMappingGateCoordinator.async_set_mapping_gate(coordinator, 1, True)

    assert coordinator.state.mapping_gates[1].state is True
    assert coordinator.client.async_send_flexml.await_count == 2
    coordinator.async_set_updated_data.assert_called_once_with(coordinator.state)


@pytest.mark.asyncio
async def test_set_mapping_gate_rejects_unknown_and_unconfirmed_state() -> None:
    """Mapping Gate control rejects unknown IDs and a refresh that does not confirm state."""
    coordinator = MagicMock()
    coordinator.state = SpcState()

    with pytest.raises(ValueError, match="Unknown SPC Mapping Gate 1"):
        await SpcFlexCMappingGateCoordinator.async_set_mapping_gate(coordinator, 1, True)

    coordinator.state.mapping_gates[1] = MappingGateState(mg_id=1, state=False)
    coordinator._client_operation_lock = _AsyncLock()
    coordinator.client.command_username = "HomeAssistant"
    coordinator.client.command_password = "MyPassword"
    coordinator.client.async_ensure_connected = AsyncMock()
    coordinator.client.async_send_flexml = AsyncMock(
        side_effect=[
            (
                '<FLEXML_REPLY VER="1.0"><REPLY_MG_CONTROL RESULT="0" '
                'CMD_RESULT="OK"><MG_CONTROL MG_ID="1" RESULT="0" />'
                "</REPLY_MG_CONTROL></FLEXML_REPLY>"
            ),
            (
                '<FLEXML_REPLY VER="1.0"><REPLY_GET_MG_STATUS RESULT="0" '
                'CMD_RESULT="OK"><MG_STATUS MG_ID="1" STATE="0" />'
                "</REPLY_GET_MG_STATUS></FLEXML_REPLY>"
            ),
        ]
    )

    with pytest.raises(ValueError, match="did not confirm"):
        await SpcFlexCMappingGateCoordinator.async_set_mapping_gate(coordinator, 1, True)


@pytest.mark.asyncio
async def test_shutdown_cancels_mapping_gate_polling() -> None:
    """Shutdown cancels the Mapping Gate task before delegating to the base coordinator."""
    coordinator = MagicMock()
    task = MagicMock()
    task.done.return_value = False
    task.cancel = MagicMock()
    task.__await__ = MagicMock(return_value=iter(()))
    coordinator._mg_poll_task = task
    coordinator._discovery_requested = True

    with patch(
        "custom_components.spc_flexc.zone_control_coordinator.SpcFlexCZoneControlCoordinator.async_shutdown",
        new=AsyncMock(),
    ) as base_shutdown:
        await SpcFlexCMappingGateCoordinator.async_shutdown(coordinator)

    assert coordinator._discovery_requested is False
    assert coordinator._mg_poll_task is None
    task.cancel.assert_called_once_with()
    base_shutdown.assert_awaited_once_with()
