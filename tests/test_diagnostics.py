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
    assert result["counts"] == {
        "areas": 1,
        "zones": 1,
        "doors": 1,
        "ats": 0,
        "xbus_devices": 1,
    }
    assert "panel" not in result
    assert "areas" not in result
    assert "zones" not in result
    assert "mains_fault" in result["faults"]
    assert "last_event" not in result["faults"]


@pytest.mark.asyncio
async def test_diagnostics_do_not_expose_private_names_or_events() -> None:
    """Sensitive panel metadata and event user names must never be exported."""
    coordinator = MagicMock()
    coordinator.client.connected = True
    coordinator.data = SpcState()
    coordinator.data.panel.raw = {
        "INSTALLATION_NAME": "PRIVATE_INSTALLATION",
        "SERIAL_NUMBER": "PRIVATE_SERIAL",
    }
    coordinator.data.areas[1] = AreaState(area_id=1, name="PRIVATE_AREA")
    coordinator.data.areas[1].raw = {
        "USER_NAME": "PRIVATE_USER",
        "last_event": {"USER_NAME": "PRIVATE_EVENT_USER"},
    }
    coordinator.data.zones[2] = ZoneState(zone_id=2, name="PRIVATE_ZONE")
    coordinator.data.faults.last_event = {\n        "USER_NAME": "PRIVATE_FAULT_EVENT_USER",\n        "ZONE_NAME": "PRIVATE_FAULT_ZONE",\n        "AREA_NAME": "PRIVATE_FAULT_AREA",\n    }\n    entry = MagicMock(runtime_data=coordinator)

    result = await async_get_config_entry_diagnostics(MagicMock(), entry)
    serialized = str(result)
    for secret in (
        "PRIVATE_INSTALLATION",
        "PRIVATE_SERIAL",
        "PRIVATE_AREA",
        "PRIVATE_USER",
        "PRIVATE_EVENT_USER",
        "PRIVATE_ZONE",
        "PRIVATE_FAULT_EVENT_USER",
        "PRIVATE_FAULT_ZONE",
        "PRIVATE_FAULT_AREA",
    ):
        assert secret not in serialized
\n    assert "last_event" not in result["faults"]\n