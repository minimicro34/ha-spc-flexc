"""Panel logs (read-only) and the get_log service."""

from datetime import UTC
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.spc_flexc.flexc.connection import FlexCCommandTimeout
from custom_components.spc_flexc.flexc.flexml import FlexMLError, FlexMLReplyError
from custom_components.spc_flexc.flexc.logs import build_log_command, parse_log
from custom_components.spc_flexc.services import GET_LOG_SCHEMA, _async_get_log

# Record shapes as sent by an SPC4300 (firmware 3.16); values are placeholders.
ACCESS_LOG = (
    '<FLEXML_REPLY VER="1.0"><REPLY_GET_ACCESS_LOG RESULT="0" CMD_RESULT="OK">'
    '<ACCESS_LOG_EVENT TIME="15411820102026" TYPE="5" DOOR_ID="3" '
    'DOOR_NAME="Front door" LOG_TEXT="Exit button"  />'
    '<ACCESS_LOG_EVENT TIME="19270622102026" TYPE="1" DOOR_ID="3" '
    'DOOR_NAME="Front door" USER_ID="4" USER_NAME="Guest" '
    'LOG_TEXT="Entry granted (Guest)"  />'
    '<ACCESS_LOG_EVENT TIME="19300022102026" TYPE="2" DETAIL="4" DOOR_ID="3" '
    'DOOR_NAME="Front door" LOG_TEXT="Denied"  />'
    "</REPLY_GET_ACCESS_LOG></FLEXML_REPLY>"
)
ATS_LOG = (
    '<FLEXML_REPLY VER="1.0"><REPLY_GET_FLEXC_ATS_EVENT_LOG RESULT="0" CMD_RESULT="OK">'
    '<ATS_EVENT_LOG EV_SEQ="561" EV_GRP="18" EV_ID="3014" EV_DESC="Unknown card" '
    'TIMESTAMP="16184209112026" SIA_CODE="DD" SIA_ADDRESS="3" DOOR_ID="3" '
    'DOOR_NAME="Front door" AREA_ID="1" AREA_NAME="House" CARD_FORMAT="11" '
    'CARD_BIT_COUNT="6" CARD_NUM="123456" />'
    '<ATS_EVENT_LOG EV_SEQ="562" EV_GRP="12" EV_ID="7014" EV_DESC="Gate off" '
    'TIMESTAMP="16190009112026" MG_ID="2" MG_NAME="Boiler" />'
    "</REPLY_GET_FLEXC_ATS_EVENT_LOG></FLEXML_REPLY>"
)
SYSTEM_LOG = (
    '<FLEXML_REPLY VER="1.0"><REPLY_GET_SYSTEM_LOG RESULT="0" CMD_RESULT="OK">'
    '<SYSTEM_LOG_EVENT TIME="23250703112026" RAW="076F020000000000" TEXT="Config changed" />'
    "</REPLY_GET_SYSTEM_LOG></FLEXML_REPLY>"
)
ZONE_LOG = (
    '<FLEXML_REPLY VER="1.0"><REPLY_GET_ZONE_LOG RESULT="0" CMD_RESULT="OK">'
    '<ZONE_LOG_EVENT TIME="09573506112026" ZONE_ID="25" INPUT="1" RESISTANCE="255" />'
    '<ZONE_LOG_EVENT TIME="09573606112026" ZONE_ID="25" INPUT="0" RESISTANCE="0" />'
    "</REPLY_GET_ZONE_LOG></FLEXML_REPLY>"
)


def test_build_log_commands() -> None:
    assert '<CMD_GET_ACCESS_LOG DOOR_ID="3" />' in build_log_command(
        "access", 3, "u", "p"
    )
    assert "<CMD_GET_SYSTEM_LOG />" in build_log_command("system", None, "u", "p")
    assert '<CMD_GET_FLEXC_ATS_EVENT_LOG ATS_ID="2" />' in build_log_command(
        "ats", 2, "u", "p"
    )
    with pytest.raises(ValueError):
        build_log_command("zone", None, "u", "p")


def test_access_log_newest_first_with_type_names() -> None:
    records = parse_log(ACCESS_LOG, "access", UTC)
    assert [r["type"] for r in records] == [2, 1, 5]
    assert records[0]["type_name"] == "denied"
    assert records[0]["detail"] == 4
    assert records[1]["user_name"] == "Guest"
    assert records[2]["type_name"] == "door_release"
    assert records[2]["time"] == "2026-10-20T15:41:18+00:00"


def test_ats_log_never_returns_card_data() -> None:
    records = parse_log(ATS_LOG, "ats", UTC)
    assert records[0]["event_id"] == 7014
    assert records[0]["mapping_gate_name"] == "Boiler"
    unknown_card = records[1]
    assert unknown_card["event_id"] == 3014
    assert not any("card" in key for key in unknown_card)
    assert "123456" not in str(records)


def test_system_and_zone_logs() -> None:
    assert parse_log(SYSTEM_LOG, "system", UTC) == [
        {
            "time": "2026-11-03T23:25:07+00:00",
            "text": "Config changed",
            "raw": "076F020000000000",
        }
    ]
    zone = parse_log(ZONE_LOG, "zone", UTC)
    assert [(r["input"], r["resistance"]) for r in zone] == [(0, 0), (1, 255)]


def test_log_errors() -> None:
    with pytest.raises(FlexMLError):
        parse_log(SYSTEM_LOG, "access", UTC)
    with pytest.raises(FlexMLReplyError):
        parse_log(
            '<FLEXML_REPLY VER="1.0"><REPLY_GET_ZONE_LOG RESULT="12" '
            'CMD_RESULT="ERROR"/></FLEXML_REPLY>',
            "zone",
            UTC,
        )


def _hass_with_entry(coordinator) -> MagicMock:
    entry = MagicMock()
    entry.entry_id = "abc"
    entry.state = ConfigEntryState.LOADED
    entry.runtime_data = coordinator
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [entry]
    return hass


def _call(**data) -> MagicMock:
    call = MagicMock()
    call.data = GET_LOG_SCHEMA(data)
    return call


@pytest.mark.asyncio
async def test_get_log_service_limits_and_passes_id() -> None:
    coordinator = MagicMock()
    coordinator.async_read_log = AsyncMock(
        return_value=parse_log(ACCESS_LOG, "access", UTC)
    )
    result = await _async_get_log(
        _hass_with_entry(coordinator), _call(log="access", id=3, limit=2)
    )
    coordinator.async_read_log.assert_awaited_once_with("access", 3)
    assert result["count"] == 2
    assert result["total"] == 3


@pytest.mark.asyncio
async def test_get_log_service_ignores_id_for_system_log() -> None:
    coordinator = MagicMock()
    coordinator.async_read_log = AsyncMock(return_value=[])
    await _async_get_log(_hass_with_entry(coordinator), _call(log="system", id=5))
    coordinator.async_read_log.assert_awaited_once_with("system", None)


@pytest.mark.asyncio
async def test_get_log_service_errors() -> None:
    coordinator = MagicMock()
    coordinator.async_read_log = AsyncMock(side_effect=FlexCCommandTimeout("slow"))
    hass = _hass_with_entry(coordinator)
    with pytest.raises(ServiceValidationError):
        await _async_get_log(hass, _call(log="access"))
    with pytest.raises(HomeAssistantError):
        await _async_get_log(hass, _call(log="zone", id=1))
    hass.config_entries.async_entries.return_value = []
    with pytest.raises(ServiceValidationError):
        await _async_get_log(hass, _call(log="system"))


def test_access_log_types() -> None:
    """Types 6, 24 and 25 as the web page's access log shows them."""
    from custom_components.spc_flexc.flexc.logs import ACCESS_LOG_TYPES

    assert ACCESS_LOG_TYPES[6] == "door_left_open"
    assert ACCESS_LOG_TYPES[24] == "unknown_card"
    assert ACCESS_LOG_TYPES[25] == "code_lockout"


def test_ats_network_log() -> None:
    assert '<CMD_GET_FLEXC_ATS_NETWORK_LOG ATS_ID="2" />' in build_log_command(
        "ats_network", 2, "u", "p"
    )
    records = parse_log(
        '<FLEXML_REPLY VER="1.0"><REPLY_GET_FLEXC_ATS_NETWORK_LOG RESULT="0" CMD_RESULT="OK">'
        '<ATS_NETWORK_LOG ATS_ID="2" MSG_ID="4" TIMESTAMP="22114709112026" '
        'NETWORK_LOG_MESSAGE="Poll" />'
        "</REPLY_GET_FLEXC_ATS_NETWORK_LOG></FLEXML_REPLY>",
        "ats_network",
        UTC,
    )
    assert records == [
        {
            "time": "2026-11-09T22:11:47+00:00",
            "ats_id": 2,
            "message_id": 4,
            "text": "Poll",
        }
    ]


def test_atp_logs() -> None:
    assert '<CMD_GET_FLEXC_ATP_LOG ATS_ID="2" ATP_SEQ_ID="1" />' in build_log_command(
        "atp", 2, "u", "p"
    )
    assert 'ATP_SEQ_ID="3"' in build_log_command("atp_network", 2, "u", "p", 3)
    records = parse_log(
        '<FLEXML_REPLY VER="1.0"><REPLY_GET_FLEXC_ATP_LOG RESULT="0" CMD_RESULT="OK">'
        '<ATP_LOG ATS_ID="2" ATP_SEQ_ID="1" MSG_ID="43" DATA="0" TIMESTAMP="00375110112026" '
        'ATP_LOG_MESSAGE="RX ok" /></REPLY_GET_FLEXC_ATP_LOG></FLEXML_REPLY>',
        "atp",
        UTC,
    )
    assert records[0]["message_id"] == 43 and records[0]["atp"] == 1
