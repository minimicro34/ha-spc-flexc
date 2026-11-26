"""CMD_STATUS_PANEL: system alert masks give panel faults their current state."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.spc_flexc.coordinator import SpcFlexCCoordinator
from custom_components.spc_flexc.flexc.events import apply_event
from custom_components.spc_flexc.flexc.flexml import FlexMLError
from custom_components.spc_flexc.flexc.panel_status import (
    PANEL_FAULT_ALERTS,
    SYSTEM_ALERTS,
    build_status_panel_command,
    parse_status_panel,
)
from custom_components.spc_flexc.models import SpcState

# Masks captured on an SPC4300 (firmware 3.14.1) while Network Fault was
# isolated and Code Tamper inhibited; INPUT bit 0 (mains) set for the test.
STATUS = (
    '<FLEXML_REPLY VER="1.0"><REPLY_STATUS_PANEL RESULT="0" CMD_RESULT="OK">'
    '<SYSINFO TIME="00114510112026" ENGMODE="0" />'
    '<SYSALERT INPUT="00000001" ALERT="00000000" INHIBIT="00400000" ISOLATE="01000000" '
    'INHIBIT_ALLOWED_1="1" ISOLATE_ALLOWED_1="1" INHIBIT_ALLOWED_4194304="1" '
    'ISOLATE_ALLOWED_4194304="0" />'
    '<ETHERNETINFO FITTED="1" STATE="1" DHCP_ENABLED="1" IP_ADDRESS="192.0.2.10" '
    'NETMASK="255.255.255.0" GATEWAY="192.0.2.1" />'
    "</REPLY_STATUS_PANEL></FLEXML_REPLY>"
)


def test_build_status_panel_command() -> None:
    command = build_status_panel_command("user", "pass")
    assert "<CMD_STATUS_PANEL />" in command


def test_parse_status_panel_alert_masks() -> None:
    status = parse_status_panel(STATUS)
    assert status.alerts["mains_fault"].active is True
    assert status.alerts["battery_fault"].active is False
    assert status.alerts["cabinet_tamper"].active is False
    assert status.alerts["code_tamper"].inhibited is True
    assert status.alerts["network_fault"].isolated is True


def test_parse_status_panel_error_raises() -> None:
    with pytest.raises(FlexMLError):
        parse_status_panel(
            '<FLEXML_REPLY VER="1.0"><REPLY_STATUS_PANEL RESULT="103" /></FLEXML_REPLY>'
        )


def test_system_alert_bits_are_unique() -> None:
    bits = [alert.bit for alert in SYSTEM_ALERTS]
    assert len(bits) == len(set(bits))
    assert set(PANEL_FAULT_ALERTS.values()) <= {a.key for a in SYSTEM_ALERTS}


def _coordinator(reply=None, error=None) -> MagicMock:
    coordinator = MagicMock()
    coordinator.state = SpcState()
    coordinator._panel_status_unsupported = False
    coordinator._tamper_store = MagicMock()
    if error is not None:
        coordinator.client.async_get_panel_status = AsyncMock(side_effect=error)
    else:
        coordinator.client.async_get_panel_status = AsyncMock(
            return_value=parse_status_panel(reply or STATUS)
        )
    return coordinator


@pytest.mark.asyncio
async def test_poll_gives_faults_their_current_state() -> None:
    coordinator = _coordinator()
    assert coordinator.state.faults.mains_fault is None

    await SpcFlexCCoordinator._async_read_system_alerts_locked(coordinator)

    faults = coordinator.state.faults
    assert faults.mains_fault is True
    assert faults.battery_fault is False
    assert faults.panel_tamper is False
    coordinator._tamper_store.async_delay_save.assert_called_once()


@pytest.mark.asyncio
async def test_events_still_update_faults_after_a_poll() -> None:
    coordinator = _coordinator()
    await SpcFlexCCoordinator._async_read_system_alerts_locked(coordinator)

    assert apply_event(coordinator.state.faults, {"EV_ID": "5001"}) is True
    assert coordinator.state.faults.mains_fault is False
    assert apply_event(coordinator.state.faults, {"EV_ID": "5206"}) is True
    assert coordinator.state.faults.panel_tamper is True


@pytest.mark.asyncio
async def test_panel_without_status_panel_keeps_event_only_faults() -> None:
    coordinator = _coordinator(error=FlexMLError("SPC FLEXML command failed: 103"))
    coordinator.state.faults.mains_fault = True  # from an earlier event

    await SpcFlexCCoordinator._async_read_system_alerts_locked(coordinator)
    await SpcFlexCCoordinator._async_read_system_alerts_locked(coordinator)

    assert coordinator._panel_status_unsupported is True
    assert coordinator.client.async_get_panel_status.await_count == 1
    assert coordinator.state.faults.mains_fault is True
    coordinator._tamper_store.async_delay_save.assert_not_called()


@pytest.mark.asyncio
async def test_unchanged_tamper_is_not_saved_again() -> None:
    coordinator = _coordinator()
    coordinator.state.faults.panel_tamper = False

    await SpcFlexCCoordinator._async_read_system_alerts_locked(coordinator)

    coordinator._tamper_store.async_delay_save.assert_not_called()
