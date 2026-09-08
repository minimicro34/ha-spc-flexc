"""Tests for FLEXML command generation."""

import pytest

from custom_components.spc_flexc.flexc.flexml import (
    FlexMLError,
    FlexMLReplyError,
    build_area_status_batch,
    build_door_control_command,
    build_door_status_batch,
    build_panel_summary_command,
    build_zone_control_command,
    build_zone_status_batch,
    parse_alert_status,
    parse_area_status,
    parse_area_status_discovery,
    parse_door_control,
    parse_door_status_discovery,
    parse_zone_control,
    parse_zone_status_discovery,
)


def test_panel_summary_uses_configured_credentials() -> None:
    """Configured credentials must be inserted in FLEXML."""
    xml = build_panel_summary_command("HomeAssistant", "MyPassword")
    assert 'PANEL_USERNAME="HomeAssistant"' in xml
    assert 'PANEL_PASSWORD="MyPassword"' in xml
    assert "<CMD_GET_PANEL_SUMMARY />" in xml


def test_credentials_are_xml_escaped() -> None:
    """Special characters in credentials must be XML escaped."""
    xml = build_panel_summary_command("Home&Assistant", 'P@ss"word&Test')
    assert 'PANEL_USERNAME="Home&amp;Assistant"' in xml
    assert (
        "PANEL_PASSWORD='P@ss\"word&amp;Test'" in xml
        or 'PANEL_PASSWORD="P@ss&quot;word&amp;Test"' in xml
    )


def test_zone_batch_uses_credentials() -> None:
    """Zone batches must use configured credentials."""
    xml = build_zone_status_batch([1, 2], "HomeAssistant", "MyPassword")
    assert '<CMD_GET_ZONE_STATUS ZONE_ID="1" />' in xml
    assert '<CMD_GET_ZONE_STATUS ZONE_ID="2" />' in xml


def test_zone_control_builds_validated_actions() -> None:
    """Only real-panel validated inhibit actions may be emitted."""
    assert '<CMD_ZONE_CONTROL ZONE_ID="1" ACTION="0" />' in build_zone_control_command(
        1, 0, "HomeAssistant", "MyPassword"
    )
    assert '<CMD_ZONE_CONTROL ZONE_ID="1" ACTION="1" />' in build_zone_control_command(
        1, 1, "HomeAssistant", "MyPassword"
    )
    with pytest.raises(ValueError):
        build_zone_control_command(1, 2, "HomeAssistant", "MyPassword")


def test_parse_zone_control_real_panel_reply() -> None:
    """Accept the REPLY_ZONE_CONTROL shape captured from a real SPC4300."""
    response = '<FLEXML_REPLY VER="1.0"><REPLY_ZONE_CONTROL RESULT="0" CMD_RESULT="OK"><ZONE_CONTROL ZONE_ID="1" RESULT="0"/></REPLY_ZONE_CONTROL></FLEXML_REPLY>'
    parse_zone_control(response, 1)


def test_parse_zone_control_rejects_wrong_zone() -> None:
    """A successful reply for another zone must not validate the action."""
    response = '<FLEXML_REPLY VER="1.0"><REPLY_ZONE_CONTROL RESULT="0" CMD_RESULT="OK"><ZONE_CONTROL ZONE_ID="2" RESULT="0"/></REPLY_ZONE_CONTROL></FLEXML_REPLY>'
    with pytest.raises(FlexMLError):
        parse_zone_control(response, 1)


def test_parse_zone_control_rejects_result_error() -> None:
    """A failed inner ZONE_CONTROL result must raise."""
    response = '<FLEXML_REPLY VER="1.0"><REPLY_ZONE_CONTROL RESULT="0" CMD_RESULT="OK"><ZONE_CONTROL ZONE_ID="1" RESULT="54"/></REPLY_ZONE_CONTROL></FLEXML_REPLY>'
    with pytest.raises(FlexMLReplyError):
        parse_zone_control(response, 1)


def test_area_batch_uses_credentials() -> None:
    """Area batches must use configured credentials."""
    xml = build_area_status_batch([1, 2], "HomeAssistant", "MyPassword")
    assert '<CMD_GET_AREA_STATUS AREA_ID="1" />' in xml
    assert '<CMD_GET_AREA_STATUS AREA_ID="2" />' in xml


def test_door_batch_uses_credentials() -> None:
    """Door batches must use configured credentials."""
    xml = build_door_status_batch([1, 2], "HomeAssistant", "MyPassword")
    assert '<CMD_GET_DOOR_STATUS DOOR_ID="1" />' in xml
    assert '<CMD_GET_DOOR_STATUS DOOR_ID="2" />' in xml


def test_door_control_builds_spclink_actions() -> None:
    """Emit only the four door actions recovered from Vanderbilt SPCLink."""
    for action in (5, 6, 7, 8):
        xml = build_door_control_command(1, action, "HomeAssistant", "MyPassword")
        assert f'<CMD_DOOR_CONTROL DOOR_ID="1" ACTION="{action}" />' in xml
    with pytest.raises(ValueError):
        build_door_control_command(1, 4, "HomeAssistant", "MyPassword")


def test_parse_door_control_real_spc4300_reply() -> None:
    """Accept the empty successful door-control reply captured on SPC4300."""
    response = '<FLEXML_REPLY VER="1.0"><REPLY_DOOR_CONTROL RESULT="0" CMD_RESULT="OK"></REPLY_DOOR_CONTROL></FLEXML_REPLY>'
    parse_door_control(response)


def test_parse_door_control_rejects_error() -> None:
    """Reject an unsuccessful REPLY_DOOR_CONTROL."""
    response = '<FLEXML_REPLY VER="1.0"><REPLY_DOOR_CONTROL RESULT="54" CMD_RESULT="ERROR" /></FLEXML_REPLY>'
    with pytest.raises(FlexMLReplyError):
        parse_door_control(response)


def test_parse_empty_alert_status() -> None:
    """Test an empty ALERT_STATUS reply."""
    response = '<FLEXML_REPLY VER="1.0"><REPLY_GET_ALERT_STATUS RESULT="0" CMD_RESULT="OK"></REPLY_GET_ALERT_STATUS></FLEXML_REPLY>'
    assert parse_alert_status(response) == []


def test_parse_alert_status_objects() -> None:
    """Test ALERT_STATUS containing alert objects."""
    response = '<FLEXML_REPLY VER="1.0"><REPLY_GET_ALERT_STATUS RESULT="0" CMD_RESULT="OK"><ALERT EV_ID="5336" STATE="1" /><ALERT EV_ID="6100" STATE="1" /></REPLY_GET_ALERT_STATUS></FLEXML_REPLY>'
    assert parse_alert_status(response) == [
        {"EV_ID": "5336", "STATE": "1"},
        {"EV_ID": "6100", "STATE": "1"},
    ]


def test_parse_area_status_valid_and_empty_replies() -> None:
    """Keep valid areas and ignore successful empty replies."""
    response = '<FLEXML_REPLY VER="1.0"><REPLY_GET_AREA_STATUS RESULT="0" CMD_RESULT="OK"><AREA_STATUS AREA_ID="1" AREA_NAME="Logis" MODE="0" /></REPLY_GET_AREA_STATUS><REPLY_GET_AREA_STATUS RESULT="0" CMD_RESULT="OK"><AREA_STATUS AREA_ID="2" AREA_NAME="Garage" MODE="0" /></REPLY_GET_AREA_STATUS><REPLY_GET_AREA_STATUS RESULT="0" CMD_RESULT="OK"></REPLY_GET_AREA_STATUS></FLEXML_REPLY>'
    assert parse_area_status(response) == [
        {"AREA_ID": "1", "AREA_NAME": "Logis", "MODE": "0"},
        {"AREA_ID": "2", "AREA_NAME": "Garage", "MODE": "0"},
    ]


def test_area_discovery_preserves_boundary_with_valid_objects() -> None:
    """RESULT=102 must stop discovery without losing earlier objects."""
    response = '<FLEXML_REPLY VER="1.0"><REPLY_GET_AREA_STATUS RESULT="0" CMD_RESULT="OK"><AREA_STATUS AREA_ID="1" AREA_NAME="Logis" MODE="0" /></REPLY_GET_AREA_STATUS><REPLY_GET_AREA_STATUS RESULT="0" CMD_RESULT="OK" /><REPLY_GET_AREA_STATUS RESULT="102" CMD_RESULT="ERROR" /></FLEXML_REPLY>'
    result = parse_area_status_discovery(response)
    assert result.statuses == [{"AREA_ID": "1", "AREA_NAME": "Logis", "MODE": "0"}]
    assert result.boundary_reached is True


def test_zone_discovery_does_not_stop_on_empty_ok() -> None:
    """A valid but unused zone ID is a hole, not the protocol boundary."""
    response = '<FLEXML_REPLY VER="1.0"><REPLY_GET_ZONE_STATUS RESULT="0" CMD_RESULT="OK"><ZONE_STATUS ZONE_ID="5" ZONE_NAME="Zone 5" /></REPLY_GET_ZONE_STATUS><REPLY_GET_ZONE_STATUS RESULT="0" CMD_RESULT="OK" /><REPLY_GET_ZONE_STATUS RESULT="0" CMD_RESULT="OK"><ZONE_STATUS ZONE_ID="7" ZONE_NAME="Sirene" /></REPLY_GET_ZONE_STATUS></FLEXML_REPLY>'
    result = parse_zone_status_discovery(response)
    assert [zone["ZONE_ID"] for zone in result.statuses] == ["5", "7"]
    assert result.boundary_reached is False


def test_door_discovery_detects_result_102() -> None:
    """Door discovery uses the same FlexC range boundary semantics."""
    response = '<FLEXML_REPLY VER="1.0"><REPLY_GET_DOOR_STATUS RESULT="0" CMD_RESULT="OK" /><REPLY_GET_DOOR_STATUS RESULT="102" CMD_RESULT="ERROR" /></FLEXML_REPLY>'
    result = parse_door_status_discovery(response)
    assert result.statuses == []
    assert result.boundary_reached is True


def test_parse_area_status_raises_on_real_error() -> None:
    """Do not hide real AREA_STATUS command errors."""
    response = '<FLEXML_REPLY VER="1.0"><REPLY_GET_AREA_STATUS RESULT="54" CMD_RESULT="ERROR" /></FLEXML_REPLY>'
    with pytest.raises(FlexMLReplyError):
        parse_area_status(response)
