"""Regression tests for polling shutdown guards."""

from unittest.mock import MagicMock

import pytest
from homeassistant.core import CoreState

from custom_components.spc_flexc.coordinator import SpcFlexCCoordinator
from custom_components.spc_flexc.mapping_gate_coordinator import (
    SpcFlexCMappingGateCoordinator,
)
from custom_components.spc_flexc.zone_control_coordinator import (
    SpcFlexCZoneControlCoordinator,
)


@pytest.mark.parametrize(
    ("hass_state", "discovery_requested", "expected"),
    [
        (CoreState.running, True, True),
        (CoreState.running, False, False),
        (CoreState.stopping, True, False),
        (CoreState.stopped, True, False),
    ],
)
def test_polling_guard_respects_shutdown(
    hass_state: CoreState, discovery_requested: bool, expected: bool
) -> None:
    """No polling should run once Home Assistant starts stopping."""
    coordinator = MagicMock()
    coordinator.hass.state = hass_state
    coordinator._discovery_requested = discovery_requested

    assert SpcFlexCCoordinator._should_run_polling(coordinator) is expected


@pytest.mark.parametrize(
    ("coordinator_type", "schedule_method"),
    [
        (SpcFlexCCoordinator, "_schedule_zone_polling"),
        (SpcFlexCCoordinator, "_schedule_xbus_polling"),
        (SpcFlexCZoneControlCoordinator, "_schedule_door_polling"),
        (SpcFlexCMappingGateCoordinator, "_schedule_mg_polling"),
    ],
)
def test_polling_not_scheduled_while_stopping(
    coordinator_type: type, schedule_method: str
) -> None:
    """All four polling schedulers must honor the shutdown guard."""
    coordinator = MagicMock()
    coordinator._should_run_polling.return_value = False

    getattr(coordinator_type, schedule_method)(coordinator)

    coordinator.entry.async_create_background_task.assert_not_called()
