"""Tests for SPC FlexC diagnostics."""

from unittest.mock import MagicMock

import pytest

from custom_components.spc_flexc.diagnostics import async_get_config_entry_diagnostics
from custom_components.spc_flexc.models import (
    AreaState,
    DoorState,
    SpcState,
    XBusDeviceState,
    ZoneState,
)


@pytest.mark.asyncio
async def test_config_entry_diagnostics_exposes_runtime_state() -> None:
    coordinator = MagicMock()
    coordinator.client.connected = True
    coordinator.data = SpcState()
    coordinator.data.panel.raw = {"SPC_PRODUCT_TITLE": "SPC4300"}
    coordinator.data.areas[1] = AreaState(area_id=1, name="Logis")
    coordinator.data.zones[2] = ZoneState(zone_id=2, name="PIR")
    coordinator.data.doors[3] = DoorState(door_id=3, name="Garage")
    coordinator.data.xbus_devices[4] = XBusDeviceState(device_id=4, name="Keypad")
    entry = MagicMock()
    entry.runtime_data = coordinator

    result = await async_get_config_entry_diagnostics(MagicMock(), entry)

    assert result["connected"] is True
    assert result["panel"] == {"SPC_PRODUCT_TITLE": "SPC4300"}
    assert result["areas"][1].name == "Logis"
    assert result["zones"][2].name == "PIR"
    assert result["doors"][3].name == "Garage"
    assert result["xbus_devices"][4].name == "Keypad"
    assert "mains_fault" in result["faults"]
