"""Panel logs (read-only) and the get_log service."""

import asyncio
from datetime import UTC
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)

from custom_components.spc_flexc.flexc.connection import FlexCCommandTimeout
from custom_components.spc_flexc.flexc.flexml import FlexMLError, FlexMLReplyError
from custom_components.spc_flexc.flexc.logs import (
    LogReadBusy,
    build_log_command,
    parse_log,
)
from custom_components.spc_flexc.services import (
    GET_LOG_SCHEMA,
    _async_get_log,
    async_setup_services,
)

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
    # RAW is undecoded panel data and is not returned.
    assert parse_log(SYSTEM_LOG, "system", UTC) == [
        {"time": "2026-11-03T23:25:07+00:00", "text": "Config changed"}
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
    # DATA is undecoded panel data and is not returned.
    assert "data" not in records[0]


def _reply(tag: str, records: str = "") -> str:
    return (
        f'<FLEXML_REPLY VER="1.0"><{tag} RESULT="0" CMD_RESULT="OK">'
        f"{records}</{tag}></FLEXML_REPLY>"
    )


@pytest.mark.parametrize(
    ("kind", "tag"),
    [
        ("access", "REPLY_GET_ACCESS_LOG"),
        ("system", "REPLY_GET_SYSTEM_LOG"),
        ("wireless", "REPLY_GET_WIRELESS_LOG"),
        ("atp_network", "REPLY_GET_FLEXC_ATP_NETWORK_LOG"),
    ],
)
def test_empty_reply_gives_no_records(kind: str, tag: str) -> None:
    assert parse_log(_reply(tag), kind, UTC) == []


def test_invalid_or_missing_time_is_none_and_kept_last_in_panel_order() -> None:
    records = parse_log(
        _reply(
            "REPLY_GET_SYSTEM_LOG",
            '<SYSTEM_LOG_EVENT TIME="99999999999999" TEXT="bad" />'
            '<SYSTEM_LOG_EVENT TIME="23250703112026" TEXT="ok" />'
            '<SYSTEM_LOG_EVENT TEXT="none" />'
            '<SYSTEM_LOG_EVENT TIME="" TEXT="empty" />',
        ),
        "system",
        UTC,
    )
    assert [(r["text"], r["time"]) for r in records] == [
        ("ok", "2026-11-03T23:25:07+00:00"),
        ("bad", None),
        ("none", None),
        ("empty", None),
    ]


def test_panel_time_is_read_in_the_given_time_zone() -> None:
    from zoneinfo import ZoneInfo

    records = parse_log(SYSTEM_LOG, "system", ZoneInfo("Europe/Paris"))
    assert records[0]["time"] == "2026-11-03T23:25:07+01:00"


def test_wireless_log() -> None:
    assert '<CMD_GET_WIRELESS_LOG SENSOR_ID="1" />' in build_log_command(
        "wireless", None, "u", "p"
    )
    records = parse_log(
        _reply(
            "REPLY_GET_WIRELESS_LOG",
            '<WIRELESS_LOG_EVENT TIME="08150027112026" SENSOR_ID="0123456" '
            'STATUS="1" BATTERY="1" SIGNAL="7" RECEIVER_ID="0" />',
        ),
        "wireless",
        UTC,
    )
    # The radio ID stays a string, so leading zeros are kept.
    assert records == [
        {
            "time": "2026-11-27T08:15:00+00:00",
            "radio_id": "0123456",
            "status": 1,
            "battery": 1,
            "signal": 7,
            "receiver_id": 0,
        }
    ]


def test_atp_network_log() -> None:
    records = parse_log(
        _reply(
            "REPLY_GET_FLEXC_ATP_NETWORK_LOG",
            '<ATP_NETWORK_LOG ATS_ID="2" ATP_SEQ_ID="1" MSG_ID="5" '
            'TIMESTAMP="22114709112026" NETWORK_LOG_MESSAGE="Connected" />',
        ),
        "atp_network",
        UTC,
    )
    assert records == [
        {
            "time": "2026-11-09T22:11:47+00:00",
            "ats_id": 2,
            "atp": 1,
            "message_id": 5,
            "text": "Connected",
        }
    ]


def _entry(entry_id: str, coordinator) -> MagicMock:
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.state = ConfigEntryState.LOADED
    entry.runtime_data = coordinator
    return entry


def _reader() -> MagicMock:
    coordinator = MagicMock()
    coordinator.async_read_log = AsyncMock(return_value=[])
    return coordinator


@pytest.mark.asyncio
async def test_several_panels_need_an_explicit_entry() -> None:
    first, second = _reader(), _reader()
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [
        _entry("first", first),
        _entry("second", second),
    ]
    with pytest.raises(ServiceValidationError) as err:
        await _async_get_log(hass, _call(log="system"))
    assert err.value.translation_key == "several_entries"

    await _async_get_log(hass, _call(log="system", config_entry_id="second"))
    second.async_read_log.assert_awaited_once_with("system", None)
    first.async_read_log.assert_not_awaited()

    with pytest.raises(ServiceValidationError) as err:
        await _async_get_log(hass, _call(log="system", config_entry_id="other"))
    assert err.value.translation_key == "no_loaded_entry"


@pytest.mark.asyncio
async def test_command_not_in_the_command_profile() -> None:
    coordinator = MagicMock()
    coordinator.async_read_log = AsyncMock(
        side_effect=FlexMLReplyError("not permitted", code="65")
    )
    with pytest.raises(HomeAssistantError) as err:
        await _async_get_log(_hass_with_entry(coordinator), _call(log="system"))
    assert err.value.translation_key == "log_not_permitted"
    assert err.value.translation_placeholders == {
        "log": "system",
        "command": "GET_SYSTEM_LOG",
    }


@pytest.mark.asyncio
async def test_other_reply_error_is_a_read_failure() -> None:
    coordinator = MagicMock()
    coordinator.async_read_log = AsyncMock(
        side_effect=FlexMLReplyError("missing parameter", code="102")
    )
    with pytest.raises(HomeAssistantError) as err:
        await _async_get_log(_hass_with_entry(coordinator), _call(log="system"))
    assert err.value.translation_key == "log_read_failed"


@pytest.mark.asyncio
async def test_busy_reader_is_reported() -> None:
    coordinator = MagicMock()
    coordinator.async_read_log = AsyncMock(side_effect=LogReadBusy("system"))
    with pytest.raises(HomeAssistantError) as err:
        await _async_get_log(_hass_with_entry(coordinator), _call(log="system"))
    assert err.value.translation_key == "log_read_busy"


@pytest.mark.asyncio
async def test_one_log_read_at_a_time_per_panel() -> None:
    from custom_components.spc_flexc.coordinator import SpcFlexCCoordinator

    release = asyncio.Event()

    async def slow_send(command: str) -> str:
        await release.wait()
        return _reply("REPLY_GET_SYSTEM_LOG")

    coordinator = SpcFlexCCoordinator.__new__(SpcFlexCCoordinator)
    coordinator._client_operation_lock = asyncio.Lock()
    coordinator._log_read_lock = asyncio.Lock()
    coordinator.client = MagicMock()
    coordinator.client.async_ensure_connected = AsyncMock()
    coordinator.client.command_username = "u"
    coordinator.client.command_password = "p"
    coordinator.client.async_send_flexml = slow_send

    first = asyncio.create_task(coordinator.async_read_log("system"))
    await asyncio.sleep(0)
    with pytest.raises(LogReadBusy):
        await coordinator.async_read_log("access", 1)
    release.set()
    assert await first == []
    # Free again once the first read has finished.
    assert await coordinator.async_read_log("system") == []


def _registered_handler(hass: MagicMock):
    hass.services.has_service.return_value = False
    async_setup_services(hass)
    args = hass.services.async_register.call_args.args
    return args[2]


@pytest.mark.asyncio
async def test_get_log_is_for_administrators_only() -> None:
    hass = MagicMock()
    handler = _registered_handler(hass)
    user = MagicMock()
    user.is_admin = False
    hass.auth.async_get_user = AsyncMock(return_value=user)
    call = _call(log="system")
    call.context.user_id = "user"
    with pytest.raises(Unauthorized):
        await handler(call)
    hass.async_run_hass_job.assert_not_called()


@pytest.mark.asyncio
async def test_get_log_runs_for_an_administrator() -> None:
    hass = MagicMock()
    handler = _registered_handler(hass)
    user = MagicMock()
    user.is_admin = True
    hass.auth.async_get_user = AsyncMock(return_value=user)
    coordinator = _reader()
    hass.config_entries.async_entries.return_value = [_entry("abc", coordinator)]
    hass.async_run_hass_job = lambda job, call: asyncio.ensure_future(job.target(call))
    call = _call(log="system")
    call.context.user_id = "admin"
    result = await handler(call)
    assert result["log"] == "system"
    coordinator.async_read_log.assert_awaited_once_with("system", None)
