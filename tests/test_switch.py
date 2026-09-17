"""Tests for SPC FlexC switch entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.spc_flexc.models import (
    AreaState,
    MappingGateState,
    SpcState,
    ZoneState,
)
from custom_components.spc_flexc.switch import (
    SpcMappingGateSwitch,
    SpcZoneInhibitionSwitch,
    SpcZoneIsolationSwitch,
    async_setup_entry,
)


def _coordinator() -> MagicMock:
    coordinator = MagicMock()
    coordinator.entry.entry_id = "test"
    coordinator.entry.data = {"host": "192.0.2.1"}
    coordinator.data = SpcState()
    coordinator.data.areas[1] = AreaState(area_id=1, name="Logis")
    return coordinator


def test_zone_inhibition_switch_state_attributes_and_availability() -> None:
    coordinator = _coordinator()
    coordinator.data.zones[1] = ZoneState(
        zone_id=1,
        name="PIR",
        area_id=1,
        inhibit_allowed=True,
        raw={"INHIBIT_ALLOWED": "1"},
    )
    switch = SpcZoneInhibitionSwitch(coordinator, 1)

    assert switch.is_on is False
    assert switch.available is True
    assert switch.extra_state_attributes == {
        "zone_id": 1,
        "inhibit_allowed": True,
        "deinhibit_allowed": False,
    }

    del coordinator.data.zones[1]
    assert switch.is_on is None
    assert switch.available is False
    assert switch.extra_state_attributes == {}


@pytest.mark.asyncio
async def test_zone_inhibition_switch_controls_zone() -> None:
    coordinator = _coordinator()
    coordinator.async_inhibit_zone = AsyncMock()
    coordinator.async_deinhibit_zone = AsyncMock()
    coordinator.data.zones[1] = ZoneState(zone_id=1, raw={"INHIBIT_ALLOWED": "1"})
    switch = SpcZoneInhibitionSwitch(coordinator, 1)

    await switch.async_turn_on()
    await switch.async_turn_off()

    coordinator.async_inhibit_zone.assert_awaited_once_with(1)
    coordinator.async_deinhibit_zone.assert_awaited_once_with(1)


def test_zone_isolation_switch_state_attributes_and_availability() -> None:
    coordinator = _coordinator()
    coordinator.data.zones[1] = ZoneState(
        zone_id=1,
        name="PIR",
        area_id=1,
        isolate_allowed=True,
        raw={"ISOLATE_ALLOWED": "1"},
    )
    switch = SpcZoneIsolationSwitch(coordinator, 1)

    assert switch.is_on is False
    assert switch.available is True
    assert switch.extra_state_attributes == {
        "zone_id": 1,
        "isolate_allowed": True,
        "deisolate_allowed": False,
    }

    coordinator.data.zones[1].raw = {
        "ISOLATED": "1",
        "DEISOLATE_ALLOWED": "1",
    }
    assert switch.is_on is True
    assert switch.extra_state_attributes["deisolate_allowed"] is True

    del coordinator.data.zones[1]
    assert switch.is_on is None
    assert switch.available is False
    assert switch.extra_state_attributes == {}


@pytest.mark.asyncio
async def test_zone_isolation_switch_controls_zone() -> None:
    coordinator = _coordinator()
    coordinator.async_isolate_zone = AsyncMock()
    coordinator.async_deisolate_zone = AsyncMock()
    coordinator.data.zones[1] = ZoneState(zone_id=1, raw={"ISOLATE_ALLOWED": "1"})
    switch = SpcZoneIsolationSwitch(coordinator, 1)

    await switch.async_turn_on()
    await switch.async_turn_off()

    coordinator.async_isolate_zone.assert_awaited_once_with(1)
    coordinator.async_deisolate_zone.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_mapping_gate_switch_state_attributes_and_control() -> None:
    coordinator = _coordinator()
    coordinator.async_set_mapping_gate = AsyncMock()
    coordinator.data.mapping_gates[2] = MappingGateState(
        mg_id=2, name="Portail", state=True
    )
    switch = SpcMappingGateSwitch(coordinator, 2)

    assert switch.is_on is True
    assert switch.available is True
    assert switch.extra_state_attributes == {"mg_id": 2, "mg_name": "Portail"}

    await switch.async_turn_off()
    await switch.async_turn_on()
    coordinator.async_set_mapping_gate.assert_any_await(2, False)
    coordinator.async_set_mapping_gate.assert_any_await(2, True)

    del coordinator.data.mapping_gates[2]
    assert switch.is_on is None
    assert switch.available is False
    assert switch.extra_state_attributes == {}


@pytest.mark.asyncio
async def test_setup_entry_adds_switches_dynamically_without_duplicates() -> None:
    """Eligible zones and outputs appear as discovery data arrives, only once."""
    coordinator = _coordinator()
    coordinator.data.zones[1] = ZoneState(
        zone_id=1,
        name="PIR",
        area_id=1,
        inhibit_allowed=True,
        isolate_allowed=True,
        raw={"INHIBIT_ALLOWED": "1", "ISOLATE_ALLOWED": "1"},
    )
    coordinator.data.mapping_gates[2] = MappingGateState(
        mg_id=2, name="Portail", state=False
    )
    listeners: list[object] = []

    def add_listener(callback):
        listeners.append(callback)
        return MagicMock()

    coordinator.async_add_listener.side_effect = add_listener
    entry = MagicMock()
    entry.runtime_data = coordinator
    async_add_entities = MagicMock()

    await async_setup_entry(MagicMock(), entry, async_add_entities)

    first_entities = async_add_entities.call_args.args[0]
    assert [type(entity) for entity in first_entities] == [
        SpcZoneInhibitionSwitch,
        SpcZoneIsolationSwitch,
        SpcMappingGateSwitch,
    ]
    assert len(listeners) == 1

    # Re-running the listener with unchanged coordinator data must not duplicate entities.
    listeners[0]()
    assert async_add_entities.call_count == 1

    # A later discovery update adds only newly eligible entities.
    coordinator.data.zones[2] = ZoneState(
        zone_id=2,
        name="Door",
        inhibited=True,
        isolated=True,
        raw={"INHIBITED": "1", "ISOLATED": "1"},
    )
    coordinator.data.mapping_gates[3] = MappingGateState(
        mg_id=3, name="Light", state=True
    )
    listeners[0]()

    second_entities = async_add_entities.call_args.args[0]
    assert [type(entity) for entity in second_entities] == [
        SpcZoneInhibitionSwitch,
        SpcZoneIsolationSwitch,
        SpcMappingGateSwitch,
    ]
    assert [entity.zone_id for entity in second_entities[:2]] == [2, 2]
    assert second_entities[2].mg_id == 3
    assert async_add_entities.call_count == 2
