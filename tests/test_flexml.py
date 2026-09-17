"""Tests for FLEXML command generation."""

import pytest

from custom_components.spc_flexc.flexc.flexml import (
    FlexMLError,
    FlexMLReplyError,
    build_area_status_batch,
    build_door_control_command,
    build_door_status_batch,
    build_panel_summary_command,
    build_xbus_status_command,
    build_zone_control_command,
    build_zone_status_batch,
    parse_alert_status,
    parse_area_status,
    parse_area_status_discovery,
    parse_door_control,
    parse_door_status_discovery,
    parse_xbus_status,
    parse_zone_control,
    parse_zone_status_discovery,
)


def test_panel_summary_uses_configured_credentials() -> None:
    xml = build_panel_summary_command("HomeAssistant", "MyPassword")
    assert 'PANEL_USERNAME="HomeAssistant"' in xml
    assert 'PANEL_PASSWORD="MyPassword"' in xml
    assert "<CMD_GET_PANEL_SUMMARY />" in xml


def test_credentials_are_xml_escaped() -> None:
    xml = build_panel_summary_command("Home&Assistant", 'P@ss"word&Test')
    assert 'PANEL_USERNAME="Home&amp;Assistant"' in xml
    assert (
        "PANEL_PASSWORD='P@ss\"word&amp;Test'" in xml
        or 'PANEL_PASSWORD="P@ss&quot;word&amp;Test"' in xml
    )


def test_zone_batch_uses_credentials() -> None:
    xml = build_zone_status_batch([1, 2], "HomeAssistant", "MyPassword")
    assert '<CMD_GET_ZONE_STATUS ZONE_ID="1" />' in xml
    assert '<CMD_GET_ZONE_STATUS ZONE_ID="2" />' in xml


def test_zone_control_builds_validated_actions() -> None:
    """All four real-panel validated zone actions may be emitted."""
    for action in (0, 1, 2, 3):
        xml = build_zone_control_command(1, action, "HomeAssistant", "MyPassword")
        assert f'<CMD_ZONE_CONTROL ZONE_ID="1" ACTION="{action}" />' in xml
    with pytest.raises(ValueError):
        build_zone_control_command(1, 4, "HomeAssistant", "MyPassword")


def test_parse_zone_control_real_panel_reply() -> None:
    response = '<FLEXML_REPLY VER="1.0"><REPLY_ZONE_CONTROL RESULT="0" CMD_RESULT="OK"><ZONE_CONTROL ZONE_ID="1" RESULT="0"/></REPLY_ZONE_CONTROL></FLEXML_REPLY>'
    parse_zone_control(response, 1)


def test_parse_zone_control_rejects_wrong_zone() -> None:
    response = '<FLEXML_REPLY VER="1.0"><REPLY_ZONE_CONTROL RESULT="0" CMD_RESULT="OK"><ZONE_CONTROL ZONE_ID="2" RESULT="0"/></REPLY_ZONE_CONTROL></FLEXML_REPLY>'
    with pytest.raises(FlexMLError):
        parse_zone_control(response, 1)


def test_parse_zone_control_rejects_result_error() -> None:
    response = '<FLEXML_REPLY VER="1.0"><REPLY_ZONE_CONTROL RESULT="0" CMD_RESULT="OK"><ZONE_CONTROL ZONE_ID="1" RESULT="54"/></REPLY_ZONE_CONTROL></FLEXML_REPLY>'
    with pytest.raises(FlexMLReplyError):
        parse_zone_control(response, 1)


def test_area_batch_uses_credentials() -> None:
    xml = build_area_status_batch([1, 2], "HomeAssistant", "MyPassword")
    assert '<CMD_GET_AREA_STATUS AREA_ID="1" />' in xml
    assert '<CMD_GET_AREA_STATUS AREA_ID="2" />' in xml


def test_door_batch_uses_credentials() -> None:
    xml = build_door_status_batch([1, 2], "HomeAssistant", "MyPassword")
    assert '<CMD_GET_DOOR_STATUS DOOR_ID="1" />' in xml
    assert '<CMD_GET_DOOR_STATUS DOOR_ID="2" />' in xml


def test_door_control_builds_spclink_actions() -> None:
    for action in (5, 6, 7, 8):
        xml = build_door_control_command(1, action, "HomeAssistant", "MyPassword")
        assert f'<CMD_DOOR_CONTROL DOOR_ID="1" ACTION="{action}" />' in xml
    with pytest.raises(ValueError):
        build_door_control_command(1, 4, "HomeAssistant", "MyPassword")


def test_parse_door_control_real_spc4300_reply() -> None:
    response = '<FLEXML_REPLY VER="1.0"><REPLY_DOOR_CONTROL RESULT="0" CMD_RESULT="OK"></REPLY_DOOR_CONTROL></FLEXML_REPLY>'
    parse_door_control(response)


def test_parse_door_control_rejects_error() -> None:
    response = '<FLEXML_REPLY VER="1.0"><REPLY_DOOR_CONTROL RESULT="54" CMD_RESULT="ERROR" /></FLEXML_REPLY>'
    with pytest.raises(FlexMLReplyError):
        parse_door_control(response)


def test_parse_empty_alert_status() -> None:
    response = '<FLEXML_REPLY VER="1.0"><REPLY_GET_ALERT_STATUS RESULT="0" CMD_RESULT="OK"></REPLY_GET_ALERT_STATUS></FLEXML_REPLY>'
    assert parse_alert_status(response) == []


def test_parse_alert_status_objects() -> None:
    response = '<FLEXML_REPLY VER="1.0"><REPLY_GET_ALERT_STATUS RESULT="0" CMD_RESULT="OK"><ALERT EV_ID="5336" STATE="1" /><ALERT EV_ID="6100" STATE="1" /></REPLY_GET_ALERT_STATUS></FLEXML_REPLY>'
    assert parse_alert_status(response) == [
        {"EV_ID": "5336", "STATE": "1"},
        {"EV_ID": "6100", "STATE": "1"},
    ]


def test_parse_area_status_valid_and_empty_replies() -> None:
    response = '<FLEXML_REPLY VER="1.0"><REPLY_GET_AREA_STATUS RESULT="0" CMD_RESULT="OK"><AREA_STATUS AREA_ID="1" AREA_NAME="Logis" MODE="0" /></REPLY_GET_AREA_STATUS><REPLY_GET_AREA_STATUS RESULT="0" CMD_RESULT="OK"><AREA_STATUS AREA_ID="2" AREA_NAME="Garage" MODE="0" /></REPLY_GET_AREA_STATUS><REPLY_GET_AREA_STATUS RESULT="0" CMD_RESULT="OK"></REPLY_GET_AREA_STATUS></FLEXML_REPLY>'
    assert parse_area_status(response) == [
        {"AREA_ID": "1", "AREA_NAME": "Logis", "MODE": "0"},
        {"AREA_ID": "2", "AREA_NAME": "Garage", "MODE": "0"},
    ]


def test_area_discovery_preserves_boundary_with_valid_objects() -> None:
    response = '<FLEXML_REPLY VER="1.0"><REPLY_GET_AREA_STATUS RESULT="0" CMD_RESULT="OK"><AREA_STATUS AREA_ID="1" AREA_NAME="Logis" MODE="0" /></REPLY_GET_AREA_STATUS><REPLY_GET_AREA_STATUS RESULT="0" CMD_RESULT="OK" /><REPLY_GET_AREA_STATUS RESULT="102" CMD_RESULT="ERROR" /></FLEXML_REPLY>'
    result = parse_area_status_discovery(response)
    assert result.statuses == [{"AREA_ID": "1", "AREA_NAME": "Logis", "MODE": "0"}]
    assert result.boundary_reached is True


def test_zone_discovery_does_not_stop_on_empty_ok() -> None:
    response = '<FLEXML_REPLY VER="1.0"><REPLY_GET_ZONE_STATUS RESULT="0" CMD_RESULT="OK"><ZONE_STATUS ZONE_ID="5" ZONE_NAME="Zone 5" /></REPLY_GET_ZONE_STATUS><REPLY_GET_ZONE_STATUS RESULT="0" CMD_RESULT="OK" /><REPLY_GET_ZONE_STATUS RESULT="0" CMD_RESULT="OK"><ZONE_STATUS ZONE_ID="7" ZONE_NAME="Sirene" /></REPLY_GET_ZONE_STATUS></FLEXML_REPLY>'
    result = parse_zone_status_discovery(response)
    assert [zone["ZONE_ID"] for zone in result.statuses] == ["5", "7"]
    assert result.boundary_reached is False


def test_door_discovery_detects_result_102() -> None:
    response = '<FLEXML_REPLY VER="1.0"><REPLY_GET_DOOR_STATUS RESULT="0" CMD_RESULT="OK" /><REPLY_GET_DOOR_STATUS RESULT="102" CMD_RESULT="ERROR" /></FLEXML_REPLY>'
    result = parse_door_status_discovery(response)
    assert result.statuses == []
    assert result.boundary_reached is True


def test_parse_area_status_raises_on_real_error() -> None:
    response = '<FLEXML_REPLY VER="1.0"><REPLY_GET_AREA_STATUS RESULT="54" CMD_RESULT="ERROR" /></FLEXML_REPLY>'
    with pytest.raises(FlexMLReplyError):
        parse_area_status(response)


def test_xbus_status_command_uses_validated_read_only_command() -> None:
    xml = build_xbus_status_command("HomeAssistant", "MyPassword")
    assert "<CMD_STATUS_XBUS />" in xml
    assert 'PANEL_USERNAME="HomeAssistant"' in xml
    assert 'PANEL_PASSWORD="MyPassword"' in xml


def test_parse_xbus_status_real_panel_reply() -> None:
    response = (
        '<FLEXML_REPLY VER="1.0">'
        '<REPLY_STATUS_XBUS RESULT="0" CMD_RESULT="OK">'
        '<ENETNODE ID="1" SN="4CADF0DA" NAME="CLA 1" TYPE="1" HARDWARE_ID="1" '
        'ICOUNT="0" OCOUNT="0" VERSION="2.09 13MAR13" RF_TYPE="0" RF_VERSION="0" '
        'READER_TYPE="0" STATUS="00000004" POSITION_1="1" POSITION_2="0" '
        'INHIBIT_ALLOWED_1="1" DEISOALTE_ALLOWED_1="1" INHIBIT_ALLOWED_2="1" '
        'ISOALTE_ALLOWED_2="1" INHIBIT_ALLOWED_4="1" ISOALTE_ALLOWED_4="1" '
        'INHIBIT_ALLOWED_11="1" ISOALTE_ALLOWED_11="1" PSU_TYPE="0" AUX_VOLT="13.7V" '
        'AUX_CURR="0mA" INPUT="0002" ALERT="0000" INHIBIT="0000" ISOLATE="0002" />'
        "</REPLY_STATUS_XBUS>"
        "</FLEXML_REPLY>"
    )
    devices = parse_xbus_status(response)
    assert devices == [
        {
            "ID": "1",
            "SN": "4CADF0DA",
            "NAME": "CLA 1",
            "TYPE": "1",
            "HARDWARE_ID": "1",
            "ICOUNT": "0",
            "OCOUNT": "0",
            "VERSION": "2.09 13MAR13",
            "RF_TYPE": "0",
            "RF_VERSION": "0",
            "READER_TYPE": "0",
            "STATUS": "00000004",
            "POSITION_1": "1",
            "POSITION_2": "0",
            "INHIBIT_ALLOWED_1": "1",
            "DEISOALTE_ALLOWED_1": "1",
            "INHIBIT_ALLOWED_2": "1",
            "ISOALTE_ALLOWED_2": "1",
            "INHIBIT_ALLOWED_4": "1",
            "ISOALTE_ALLOWED_4": "1",
            "INHIBIT_ALLOWED_11": "1",
            "ISOALTE_ALLOWED_11": "1",
            "PSU_TYPE": "0",
            "AUX_VOLT": "13.7V",
            "AUX_CURR": "0mA",
            "INPUT": "0002",
            "ALERT": "0000",
            "INHIBIT": "0000",
            "ISOLATE": "0002",
        }
    ]


def test_parse_xbus_status_supports_multiple_nodes() -> None:
    response = '<FLEXML_REPLY VER="1.0"><REPLY_STATUS_XBUS RESULT="0" CMD_RESULT="OK"><ENETNODE ID="1" NAME="Node 1"/><ENETNODE ID="2" NAME="Node 2"/></REPLY_STATUS_XBUS></FLEXML_REPLY>'
    assert parse_xbus_status(response) == [
        {"ID": "1", "NAME": "Node 1"},
        {"ID": "2", "NAME": "Node 2"},
    ]


def test_parse_xbus_status_rejects_error_reply() -> None:
    response = '<FLEXML_REPLY VER="1.0"><REPLY_STATUS_XBUS RESULT="54" CMD_RESULT="ERROR" /></FLEXML_REPLY>'
    with pytest.raises(FlexMLReplyError):
        parse_xbus_status(response)
