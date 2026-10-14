"""Regression tests for polling shutdown guards."""

import asyncio
import logging
from unittest.mock import MagicMock, patch

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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("coordinator_type", "loop_method", "task_attribute", "logger_module"),
    [
        (SpcFlexCCoordinator, "_async_zone_poll_loop", "_zone_poll_task", "coordinator"),
        (SpcFlexCCoordinator, "_async_xbus_poll_loop", "_xbus_poll_task", "coordinator"),
        (
            SpcFlexCZoneControlCoordinator,
            "_async_door_poll_loop",
            "_door_poll_task",
            "zone_control_coordinator",
        ),
        (
            SpcFlexCMappingGateCoordinator,
            "_async_mg_poll_loop",
            "_mg_poll_task",
            "mapping_gate_coordinator",
        ),
    ],
)
async def test_polling_cancelled_during_shutdown_does_not_restart_or_warn(
    coordinator_type: type,
    loop_method: str,
    task_attribute: str,
    logger_module: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Cancellation during HA shutdown must not restart any polling task."""
    coordinator = MagicMock()
    coordinator.hass.state = CoreState.running
    coordinator._discovery_requested = True
    coordinator._should_run_polling.side_effect = lambda: (
        SpcFlexCCoordinator._should_run_polling(coordinator)
    )

    with patch(
        f"custom_components.spc_flexc.{logger_module}.poll_delay_for_phase",
        return_value=3600.0,
    ):
        task = asyncio.create_task(getattr(coordinator_type, loop_method)(coordinator))
        setattr(coordinator, task_attribute, task)
        await asyncio.sleep(0)
        coordinator.hass.state = CoreState.stopping
        with caplog.at_level(
            logging.WARNING, logger=f"custom_components.spc_flexc.{logger_module}"
        ):
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    assert getattr(coordinator, task_attribute) is None
    coordinator.entry.async_create_background_task.assert_not_called()
    assert not any("polling cancelled" in record.message for record in caplog.records)
    assert not any("polling stopped unexpectedly" in record.message for record in caplog.records)
