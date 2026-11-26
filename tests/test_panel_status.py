"""CMD_STATUS_PANEL: system alert masks give panel faults their current state."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.spc_flexc.coordinator import SpcFlexCCoordinator
from custom_components.spc_flexc.flexc.connection import (
    FlexCCommandTimeout,
    FlexCConnectionError,
)
from custom_components.spc_flexc.flexc.events import apply_event
from custom_components.spc_flexc.flexc.flexml import FlexMLError, FlexMLReplyError
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


def _coordinator(reply=None, error=None, generation=1) -> MagicMock:
    coordinator = MagicMock()
    coordinator.state = SpcState()
    coordinator._panel_status_unsupported_generation = None
    coordinator._fault_event_revisions = {}
    coordinator._tamper_store = MagicMock()
    coordinator.client.session_generation = generation
    if error is not None:
        coordinator.client.async_get_panel_status = AsyncMock(side_effect=error)
    else:
        coordinator.client.async_get_panel_status = AsyncMock(
            return_value=parse_status_panel(reply or STATUS)
        )
    return coordinator


async def _read(coordinator) -> None:
    await SpcFlexCCoordinator._async_read_system_alerts_locked(coordinator)


def _status(input_mask: str = "00000001", **extra: str) -> str:
    attributes = {
        "INPUT": input_mask,
        "ALERT": "00000000",
        "INHIBIT": "00000000",
        "ISOLATE": "00000000",
        **extra,
    }
    sysalert = " ".join(
        f'{key}="{value}"' for key, value in attributes.items() if value is not None
    )
    return (
        '<FLEXML_REPLY VER="1.0"><REPLY_STATUS_PANEL RESULT="0" CMD_RESULT="OK">'
        f"<SYSALERT {sysalert} /></REPLY_STATUS_PANEL></FLEXML_REPLY>"
    )


@pytest.mark.asyncio
async def test_poll_gives_faults_their_current_state() -> None:
    coordinator = _coordinator()
    assert coordinator.state.faults.mains_fault is None

    await _read(coordinator)

    faults = coordinator.state.faults
    assert faults.mains_fault is True
    assert faults.battery_fault is False
    assert faults.panel_tamper is False
    coordinator._tamper_store.async_delay_save.assert_called_once()


@pytest.mark.asyncio
async def test_events_still_update_faults_after_a_poll() -> None:
    coordinator = _coordinator()
    await _read(coordinator)

    assert apply_event(coordinator.state.faults, {"EV_ID": "5001"}) is True
    assert coordinator.state.faults.mains_fault is False
    assert apply_event(coordinator.state.faults, {"EV_ID": "5206"}) is True
    assert coordinator.state.faults.panel_tamper is True


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["17", "65", "103"])
async def test_unsupported_reply_stops_the_read_for_this_session(code) -> None:
    error = FlexMLReplyError(f"REPLY_STATUS_PANEL failed: RESULT={code!r}", code=code)
    coordinator = _coordinator(error=error)
    coordinator.state.faults.mains_fault = True  # from an earlier event

    await _read(coordinator)
    await _read(coordinator)

    assert coordinator._panel_status_unsupported_generation == 1
    assert coordinator.client.async_get_panel_status.await_count == 1
    assert coordinator.state.faults.mains_fault is True
    coordinator._tamper_store.async_delay_save.assert_not_called()


@pytest.mark.asyncio
async def test_new_session_reads_again_after_unsupported_reply() -> None:
    error = FlexMLReplyError("REPLY_STATUS_PANEL failed: RESULT='103'", code="103")
    coordinator = _coordinator(error=error)
    await _read(coordinator)
    assert coordinator._panel_status_unsupported_generation == 1

    coordinator.client.session_generation = 2
    coordinator.client.async_get_panel_status = AsyncMock(
        return_value=parse_status_panel(STATUS)
    )
    await _read(coordinator)

    coordinator.client.async_get_panel_status.assert_awaited_once()
    assert coordinator.state.faults.mains_fault is True


@pytest.mark.asyncio
async def test_unsupported_reply_after_a_reconnect_during_the_read() -> None:
    """The session that gave the answer is the one marked, not the one before."""
    coordinator = _coordinator(generation=1)

    async def reconnect_then_unsupported():
        coordinator.client.session_generation = 2
        raise FlexMLReplyError("RESULT='103'", code="103")

    coordinator.client.async_get_panel_status = AsyncMock(
        side_effect=reconnect_then_unsupported
    )
    await _read(coordinator)
    assert coordinator._panel_status_unsupported_generation == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        FlexMLError("REPLY_STATUS_PANEL not found"),
        FlexMLReplyError("REPLY_STATUS_PANEL failed: RESULT='12'", code="12"),
        FlexMLReplyError("no code"),
        FlexCCommandTimeout("Timeout waiting for FlexC FLEXML reply"),
        FlexCConnectionError("FlexC session replaced during command"),
    ],
)
async def test_other_failures_keep_faults_and_do_not_stop_the_read(error) -> None:
    coordinator = _coordinator(error=error)
    coordinator.state.faults.mains_fault = True
    coordinator.state.faults.panel_tamper = False

    await _read(coordinator)  # does not raise
    await _read(coordinator)

    assert coordinator._panel_status_unsupported_generation is None
    assert coordinator.client.async_get_panel_status.await_count >= 2
    assert coordinator.state.faults.mains_fault is True
    assert coordinator.state.faults.panel_tamper is False
    assert coordinator.state.faults.battery_fault is None
    coordinator._tamper_store.async_delay_save.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reply",
    [
        # No SYSALERT element.
        (
            '<FLEXML_REPLY VER="1.0"><REPLY_STATUS_PANEL RESULT="0" CMD_RESULT="OK">'
            "</REPLY_STATUS_PANEL></FLEXML_REPLY>"
        ),
        _status(ISOLATE=None),  # a mask missing
        _status(input_mask=""),  # an empty mask
        _status(input_mask="zz000001"),  # not hexadecimal
    ],
)
async def test_missing_or_malformed_masks_keep_known_and_unknown_states(reply) -> None:
    coordinator = _coordinator(reply=reply)
    coordinator.state.faults.mains_fault = True
    coordinator.state.faults.panel_tamper = False
    # battery_fault stays unknown (None)

    await _read(coordinator)

    faults = coordinator.state.faults
    assert faults.mains_fault is True
    assert faults.panel_tamper is False
    assert faults.battery_fault is None
    coordinator._tamper_store.async_delay_save.assert_not_called()


@pytest.mark.asyncio
async def test_event_during_the_read_wins_over_the_older_snapshot() -> None:
    """Mains restore and cabinet tamper arrive while the read is waiting."""
    coordinator = MagicMock(spec=SpcFlexCCoordinator)
    coordinator.state = SpcState()
    coordinator._panel_status_unsupported_generation = None
    coordinator._fault_event_revisions = {}
    coordinator._tamper_store = MagicMock()
    coordinator.client = MagicMock()
    coordinator.client.session_generation = 1
    coordinator.state.faults.mains_fault = True
    coordinator.state.faults.panel_tamper = False

    async def read_with_events_in_between():
        # The panel took this snapshot before the events below.
        snapshot = parse_status_panel(_status(input_mask="00000001"))
        for event_id in ("5001", "5206"):
            SpcFlexCCoordinator._handle_flexc_event(coordinator, {"EV_ID": event_id})
        return snapshot

    coordinator.client.async_get_panel_status = AsyncMock(
        side_effect=read_with_events_in_between
    )
    await _read(coordinator)

    faults = coordinator.state.faults
    assert faults.mains_fault is False  # event, not the snapshot's True
    assert faults.panel_tamper is True  # event, not the snapshot's False
    assert faults.battery_fault is False  # no event: from the snapshot
    saved = [
        call.args[0]()
        for call in coordinator._tamper_store.async_delay_save.call_args_list
    ]
    assert saved == [{"panel_tamper": True}]


@pytest.mark.asyncio
async def test_event_before_the_read_does_not_block_the_snapshot() -> None:
    coordinator = _coordinator()
    coordinator._fault_event_revisions = {"mains_fault": 3}

    await _read(coordinator)

    assert coordinator.state.faults.mains_fault is True


@pytest.mark.asyncio
async def test_unchanged_tamper_is_not_saved_again() -> None:
    coordinator = _coordinator()
    coordinator.state.faults.panel_tamper = False

    await _read(coordinator)

    coordinator._tamper_store.async_delay_save.assert_not_called()


def test_reply_error_keeps_the_result_code() -> None:
    with pytest.raises(FlexMLReplyError) as err:
        parse_status_panel(
            '<FLEXML_REPLY VER="1.0"><REPLY_STATUS_PANEL RESULT="65" /></FLEXML_REPLY>'
        )
    assert err.value.code == "65"


@pytest.mark.asyncio
async def test_status_read_is_the_last_command_and_a_timeout_keeps_the_update() -> None:
    """The optional read runs after the area status; its timeout fails nothing."""

    class _Lock:
        async def __aenter__(self):
            return None

        async def __aexit__(self, *exc):
            return False

    coordinator = MagicMock()
    coordinator.state = SpcState()
    coordinator._client_operation_lock = _Lock()
    coordinator._ats_discovery_complete = False
    coordinator._discovery_requested = False
    coordinator.client.async_ensure_connected = AsyncMock()
    coordinator._panel_status_unsupported_generation = None
    coordinator._fault_event_revisions = {}
    coordinator.client.session_generation = 1
    coordinator._area_discovery_complete = True
    coordinator._detected_area_ids = {1}
    order: list[str] = []

    async def summary():
        order.append("summary")
        return {"INSTALLATION_NAME": "Home"}

    async def alerts():
        order.append("alerts")
        return []

    async def areas(_ids):
        order.append("areas")
        return [{"AREA_ID": "1", "AREA_NAME": "Home", "MODE": "0"}]

    async def panel_status():
        order.append("status_panel")
        raise FlexCCommandTimeout("Timeout waiting for FlexC FLEXML reply")

    coordinator.client.async_get_panel_summary = summary
    coordinator.client.async_get_alert_status = alerts
    coordinator.client.async_get_area_status = areas
    coordinator.client.async_get_panel_status = panel_status
    coordinator._async_read_system_alerts_locked = lambda: (
        SpcFlexCCoordinator._async_read_system_alerts_locked(coordinator)
    )

    state = await SpcFlexCCoordinator._async_update_data(coordinator)

    assert order == ["summary", "alerts", "areas", "status_panel"]
    assert state.areas[1].name == "Home"
    assert state.faults.mains_fault is None


@pytest.mark.parametrize("mask", ["-1", "100000000"])
def test_out_of_range_mask_is_unknown(mask: str) -> None:
    assert not parse_status_panel(_status(mask)).alerts


@pytest.mark.asyncio
async def test_diagnostic_snapshot_cleared_on_failed_read() -> None:
    coordinator = _coordinator()
    await _read(coordinator)
    assert coordinator.state.panel_status_at is not None
    assert coordinator.state.system_alerts["network_fault"]["isolated"] is True
    assert coordinator.state.panel_ethernet["IP_ADDRESS"] == "192.0.2.10"
    coordinator.client.async_get_panel_status = AsyncMock(
        side_effect=FlexMLError("invalid reply")
    )
    await _read(coordinator)
    assert coordinator.state.panel_status_at is None
    assert coordinator.state.system_alerts == {}
    assert coordinator.state.panel_ethernet == {}
    assert coordinator.state.faults.mains_fault is True
