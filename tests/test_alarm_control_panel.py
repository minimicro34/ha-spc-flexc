"""Tests for SPC FlexC alarm control panel behavior."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.spc_flexc.alarm_control_panel import (
    MODE_LABELS,
    MODE_PARTSET_A,
    MODE_PARTSET_B,
    MODE_SET,
    MODE_UNSET,
    SpcAreaAlarmControlPanel,
    SpcPanelAlarmControlPanel,
    _active_blocking_faults,
    _async_precheck_area_mode,
    _async_send_area_mode_once,
    _flexml_envelope,
    _get_area_change_mode_reason,
    _partset_name,
    _raise_not_ready,
    _reply_is_ok,
    async_setup_entry,
)
from custom_components.spc_flexc.models import AreaState, FaultState, SpcState, ZoneState


def _coordinator(*areas: AreaState) -> MagicMock:
    coordinator = MagicMock()
    coordinator.entry.entry_id = "test"
    coordinator.entry.data = {
        "command_username": "user",
        "command_password": "password",
        "host": "192.0.2.1",
    }
    coordinator.data = SpcState()
    coordinator.data.panel.serial_number = "SERIAL"
    coordinator.data.areas = {area.area_id: area for area in areas}
    coordinator.client.async_ensure_connected = AsyncMock()
    coordinator.client.async_send_flexml = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    coordinator._client_operation_lock = AsyncMockContextManager()
    return coordinator


class AsyncMockContextManager:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _precheck_reply(area_id: int, reason: str = "0") -> str:
    return (
        '<FLEXML_REPLY VER="1.0">'
        '<REPLY_GET_AREA_CHANGE_MODE_STATUS RESULT="0" CMD_RESULT="OK">'
        f'<AREA_CHANGE_MODE_STATUS AREA_ID="{area_id}" REASON_0="{reason}" />'
        "</REPLY_GET_AREA_CHANGE_MODE_STATUS>"
        "</FLEXML_REPLY>"
    )


def _mode_reply() -> str:
    return (
        '<FLEXML_REPLY VER="1.0">'
        '<REPLY_AREA_CHANGE_MODE RESULT="0" CMD_RESULT="OK" />'
        "</FLEXML_REPLY>"
    )


def test_protocol_helpers() -> None:
    envelope = _flexml_envelope('u"ser', "p&ss", '<CMD_TEST VALUE="1" />')
    assert "PANEL_USERNAME='u\"ser'" in envelope
    assert 'PANEL_PASSWORD="p&amp;ss"' in envelope
    assert _reply_is_ok(_mode_reply(), "REPLY_AREA_CHANGE_MODE") is True
    assert _reply_is_ok("not xml", "REPLY_AREA_CHANGE_MODE") is False
    assert _reply_is_ok("<FLEXML_REPLY />", "REPLY_AREA_CHANGE_MODE") is False
    assert _get_area_change_mode_reason(_precheck_reply(2, "2007"), 2) == "2007"
    assert _get_area_change_mode_reason(_precheck_reply(2), 3) is None
    assert _get_area_change_mode_reason("not xml", 2) is None


def test_area_mode_labels() -> None:
    assert MODE_LABELS == {0: "Unset", 1: "PartSetA", 2: "PartSetB", 3: "Set"}


def test_partset_names_and_faults() -> None:
    coordinator = SimpleNamespace(
        data=SimpleNamespace(
            panel=SimpleNamespace(raw={"PARTA_NAME": "Panel A", "PARTB_NAME": "  "}),
            faults=FaultState(mains_fault=True, battery_fault=True, panel_tamper=True),
        )
    )
    area = AreaState(area_id=1, raw={"PARTA_NAME": "Nuit"})
    assert _partset_name(coordinator, area, "a") == "Nuit"
    assert _partset_name(coordinator, area, "b") is None
    assert _active_blocking_faults(coordinator) == [
        "230 V mains fault",
        "panel battery fault",
        "panel tamper",
    ]


def test_not_ready_reasons() -> None:
    coordinator = _coordinator(AreaState(area_id=2, name="Garage"))
    coordinator.data.faults = FaultState(mains_fault=True, panel_tamper=True)
    coordinator.data.zones[5] = ZoneState(zone_id=5, name="Fenêtre")

    with pytest.raises(ServiceValidationError) as exc:
        _raise_not_ready(coordinator, 2, "2007")
    assert exc.value.translation_key == "area_not_ready_faults"

    coordinator.data.faults = FaultState()
    with pytest.raises(ServiceValidationError) as exc:
        _raise_not_ready(coordinator, 2, "2007")
    assert exc.value.translation_key == "area_not_ready"

    with pytest.raises(ServiceValidationError) as exc:
        _raise_not_ready(coordinator, 2, "10006")
    assert exc.value.translation_key == "area_not_ready_engineer"

    with pytest.raises(ServiceValidationError) as exc:
        _raise_not_ready(coordinator, 2, "1005")
    assert exc.value.translation_key == "area_not_ready_zone"
    assert exc.value.translation_placeholders["zone"] == "Fenêtre"

    with pytest.raises(ServiceValidationError) as exc:
        _raise_not_ready(coordinator, 99, "n/a")
    assert exc.value.translation_key == "area_not_ready"
    assert exc.value.translation_placeholders["area"] == "Area 99"


@pytest.mark.asyncio
async def test_precheck_and_single_mode_command() -> None:
    coordinator = _coordinator(AreaState(area_id=1, name="Logis"))
    coordinator.client.async_send_flexml.side_effect = [_precheck_reply(1), _mode_reply()]

    await _async_precheck_area_mode(coordinator, 1, MODE_SET, "user", "password")
    await _async_send_area_mode_once(coordinator, 1, MODE_SET, "user", "password")
    assert coordinator.client.async_send_flexml.await_count == 2

    coordinator.client.async_send_flexml = AsyncMock(return_value="bad")
    with pytest.raises(HomeAssistantError):
        await _async_precheck_area_mode(coordinator, 1, MODE_SET, "user", "password")
    with pytest.raises(HomeAssistantError):
        await _async_send_area_mode_once(coordinator, 1, MODE_SET, "user", "password")

    coordinator.client.async_send_flexml = AsyncMock(return_value=_precheck_reply(1, "2007"))
    with pytest.raises(ServiceValidationError):
        await _async_precheck_area_mode(coordinator, 1, MODE_SET, "user", "password")


def test_area_entity_states_features_and_attributes() -> None:
    area = AreaState(
        area_id=1,
        name="Logis",
        mode=MODE_UNSET,
        partset_a_enabled=True,
        partset_b_enabled=True,
        raw={"PARTA_NAME": "Nuit", "PARTB_NAME": "Soir"},
    )
    coordinator = _coordinator(area)
    entity = SpcAreaAlarmControlPanel(coordinator, 1)

    assert entity.available is True
    assert entity.alarm_state == AlarmControlPanelState.DISARMED
    assert entity.supported_features == (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )
    assert entity.extra_state_attributes["partset_a_name"] == "Nuit"

    for mode, state in (
        (MODE_PARTSET_A, AlarmControlPanelState.ARMED_HOME),
        (MODE_PARTSET_B, AlarmControlPanelState.ARMED_NIGHT),
        (MODE_SET, AlarmControlPanelState.ARMED_AWAY),
        (99, None),
    ):
        area.mode = mode
        assert entity.alarm_state == state

    del coordinator.data.areas[1]
    assert entity.available is False
    assert entity.alarm_state is None
    assert entity.extra_state_attributes == {}


@pytest.mark.asyncio
async def test_area_commands_and_validation() -> None:
    area = AreaState(area_id=1, name="Logis", partset_a_enabled=True, partset_b_enabled=True)
    coordinator = _coordinator(area)
    entity = SpcAreaAlarmControlPanel(coordinator, 1)

    with (
        patch(
            "custom_components.spc_flexc.alarm_control_panel._async_precheck_area_mode",
            new=AsyncMock(),
        ) as precheck,
        patch(
            "custom_components.spc_flexc.alarm_control_panel._async_send_area_mode_once",
            new=AsyncMock(),
        ) as send,
    ):
        await entity.async_alarm_disarm()
        await entity.async_alarm_arm_away()
        await entity.async_alarm_arm_home()
        await entity.async_alarm_arm_night()
    assert precheck.await_count == 4
    assert send.await_count == 4
    assert coordinator.async_request_refresh.await_count == 4

    area.partset_a_enabled = False
    with pytest.raises(ServiceValidationError) as exc:
        await entity.async_alarm_arm_home()
    assert exc.value.translation_key == "partset_a_not_supported"
    area.partset_b_enabled = False
    with pytest.raises(ServiceValidationError) as exc:
        await entity.async_alarm_arm_night()
    assert exc.value.translation_key == "partset_b_not_supported"

    del coordinator.data.areas[1]
    with pytest.raises(HomeAssistantError):
        await entity.async_alarm_arm_away()


def test_panel_entity_states_and_attributes() -> None:
    coordinator = _coordinator(
        AreaState(area_id=2, name="Garage", mode=MODE_UNSET),
        AreaState(area_id=1, name="Logis", mode=MODE_UNSET),
    )
    entity = SpcPanelAlarmControlPanel(coordinator)
    assert entity.available is True
    assert entity.alarm_state == AlarmControlPanelState.DISARMED
    assert list(entity.extra_state_attributes["areas"]) == ["1", "2"]

    for area in coordinator.data.areas.values():
        area.mode = MODE_SET
    assert entity.alarm_state == AlarmControlPanelState.ARMED_AWAY
    coordinator.data.areas[2].mode = MODE_UNSET
    assert entity.alarm_state is None
    coordinator.data.areas.clear()
    assert entity.available is False
    assert entity.alarm_state is None


@pytest.mark.asyncio
async def test_panel_global_arm_and_disarm() -> None:
    coordinator = _coordinator(
        AreaState(area_id=1, name="Logis"), AreaState(area_id=2, name="Garage")
    )
    entity = SpcPanelAlarmControlPanel(coordinator)

    with (
        patch(
            "custom_components.spc_flexc.alarm_control_panel._async_precheck_area_mode",
            new=AsyncMock(),
        ) as precheck,
        patch(
            "custom_components.spc_flexc.alarm_control_panel._async_send_area_mode_once",
            new=AsyncMock(),
        ) as send,
    ):
        await entity.async_alarm_arm_away()
        assert precheck.await_count == 2
        assert send.await_count == 2
        await entity.async_alarm_disarm()
        assert precheck.await_count == 4
        assert send.await_count == 4

    coordinator.data.areas.clear()
    with pytest.raises(HomeAssistantError):
        await entity.async_alarm_arm_away()
    with pytest.raises(HomeAssistantError):
        await entity.async_alarm_disarm()


@pytest.mark.asyncio
async def test_panel_partial_failures_are_reported() -> None:
    coordinator = _coordinator(
        AreaState(area_id=1, name="Logis"), AreaState(area_id=2, name="Garage")
    )
    entity = SpcPanelAlarmControlPanel(coordinator)

    with (
        patch(
            "custom_components.spc_flexc.alarm_control_panel._async_precheck_area_mode",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.spc_flexc.alarm_control_panel._async_send_area_mode_once",
            new=AsyncMock(side_effect=[None, HomeAssistantError("refused")]),
        ),
    ):
        with pytest.raises(ServiceValidationError) as exc:
            await entity.async_alarm_arm_away()
    assert exc.value.translation_key == "global_arm_incomplete"
    assert exc.value.translation_placeholders["areas"] == "Logis"

    with (
        patch(
            "custom_components.spc_flexc.alarm_control_panel._async_precheck_area_mode",
            new=AsyncMock(side_effect=[HomeAssistantError("blocked"), None]),
        ),
        patch(
            "custom_components.spc_flexc.alarm_control_panel._async_send_area_mode_once",
            new=AsyncMock(),
        ),
    ):
        with pytest.raises(ServiceValidationError) as exc:
            await entity.async_alarm_disarm()
    assert exc.value.translation_key == "global_disarm_incomplete"
    assert "Logis: blocked" in exc.value.translation_placeholders["errors"]


@pytest.mark.asyncio
async def test_setup_entry_adds_new_areas_once() -> None:
    coordinator = _coordinator(AreaState(area_id=1, name="Logis"))
    entry = MagicMock()
    entry.runtime_data = coordinator
    listeners: list[object] = []
    coordinator.async_add_listener.side_effect = lambda callback: (
        listeners.append(callback) or MagicMock()
    )
    batches: list[list[object]] = []

    await async_setup_entry(
        MagicMock(), entry, lambda entities: batches.append(list(entities))
    )
    assert [len(batch) for batch in batches] == [1, 1]
    listeners[0]()
    assert len(batches) == 2
    coordinator.data.areas[2] = AreaState(area_id=2, name="Garage")
    listeners[0]()
    assert len(batches[2]) == 1
