"""Tests for FLEXML command generation."""

import pytest

from custom_components.spc_flexc.flexc.flexml import (
    FlexMLReplyError,
    build_area_status_batch,
    build_panel_summary_command,
    build_zone_status_batch,
    parse_alert_status,
    parse_area_status,
)


def test_panel_summary_uses_configured_credentials() -> None:
    """Configured credentials must be inserted in FLEXML."""
    xml = build_panel_summary_command(
        "HomeAssistant",
        "MyPassword",
    )

    assert 'PANEL_USERNAME="HomeAssistant"' in xml
    assert 'PANEL_PASSWORD="MyPassword"' in xml
    assert "<CMD_GET_PANEL_SUMMARY />" in xml


def test_credentials_are_xml_escaped() -> None:
    """Special characters in credentials must be XML escaped."""
    xml = build_panel_summary_command(
        "Home&Assistant",
        'P@ss"word&Test',
    )

    assert 'PANEL_USERNAME="Home&amp;Assistant"' in xml
    assert (
        "PANEL_PASSWORD='P@ss\"word&amp;Test'" in xml
        or 'PANEL_PASSWORD="P@ss&quot;word&amp;Test"' in xml
    )


def test_zone_batch_uses_credentials() -> None:
    """Zone batches must use configured credentials."""
    xml = build_zone_status_batch(
        [1, 2],
        "HomeAssistant",
        "MyPassword",
    )

    assert 'PANEL_USERNAME="HomeAssistant"' in xml
    assert 'PANEL_PASSWORD="MyPassword"' in xml
    assert '<CMD_GET_ZONE_STATUS ZONE_ID="1" />' in xml
    assert '<CMD_GET_ZONE_STATUS ZONE_ID="2" />' in xml


def test_area_batch_uses_credentials() -> None:
    """Area batches must use configured credentials."""
    xml = build_area_status_batch(
        [1, 2],
        "HomeAssistant",
        "MyPassword",
    )

    assert 'PANEL_USERNAME="HomeAssistant"' in xml
    assert 'PANEL_PASSWORD="MyPassword"' in xml
    assert '<CMD_GET_AREA_STATUS AREA_ID="1" />' in xml
    assert '<CMD_GET_AREA_STATUS AREA_ID="2" />' in xml


def test_parse_empty_alert_status() -> None:
    """Test an empty ALERT_STATUS reply."""
    response = (
        '<FLEXML_REPLY VER="1.0">'
        "<REPLY_GET_ALERT_STATUS "
        'RESULT="0" CMD_RESULT="OK">'
        "</REPLY_GET_ALERT_STATUS>"
        "</FLEXML_REPLY>"
    )

    assert parse_alert_status(response) == []


def test_parse_alert_status_objects() -> None:
    """Test ALERT_STATUS containing alert objects."""
    response = (
        '<FLEXML_REPLY VER="1.0">'
        "<REPLY_GET_ALERT_STATUS "
        'RESULT="0" CMD_RESULT="OK">'
        '<ALERT EV_ID="5336" STATE="1" />'
        '<ALERT EV_ID="6100" STATE="1" />'
        "</REPLY_GET_ALERT_STATUS>"
        "</FLEXML_REPLY>"
    )

    alerts = parse_alert_status(response)

    assert alerts == [
        {
            "EV_ID": "5336",
            "STATE": "1",
        },
        {
            "EV_ID": "6100",
            "STATE": "1",
        },
    ]


def test_parse_area_status_valid_and_empty_replies() -> None:
    """Keep valid areas and ignore successful empty replies."""
    response = (
        '<FLEXML_REPLY VER="1.0">'
        '<REPLY_GET_AREA_STATUS RESULT="0" CMD_RESULT="OK">'
        '<AREA_STATUS AREA_ID="1" AREA_NAME="Logis" MODE="0" />'
        "</REPLY_GET_AREA_STATUS>"
        '<REPLY_GET_AREA_STATUS RESULT="0" CMD_RESULT="OK">'
        '<AREA_STATUS AREA_ID="2" AREA_NAME="Garage" MODE="0" />'
        "</REPLY_GET_AREA_STATUS>"
        '<REPLY_GET_AREA_STATUS RESULT="0" CMD_RESULT="OK">'
        "</REPLY_GET_AREA_STATUS>"
        "</FLEXML_REPLY>"
    )

    assert parse_area_status(response) == [
        {
            "AREA_ID": "1",
            "AREA_NAME": "Logis",
            "MODE": "0",
        },
        {
            "AREA_ID": "2",
            "AREA_NAME": "Garage",
            "MODE": "0",
        },
    ]


def test_parse_area_status_ignores_result_102() -> None:
    """Keep valid areas when a later reply returns RESULT=102."""
    response = (
        '<FLEXML_REPLY VER="1.0">'
        '<REPLY_GET_AREA_STATUS RESULT="0" CMD_RESULT="OK">'
        '<AREA_STATUS AREA_ID="1" AREA_NAME="Logis" MODE="0" />'
        "</REPLY_GET_AREA_STATUS>"
        '<REPLY_GET_AREA_STATUS RESULT="0" CMD_RESULT="OK">'
        '<AREA_STATUS AREA_ID="2" AREA_NAME="Garage" MODE="0" />'
        "</REPLY_GET_AREA_STATUS>"
        '<REPLY_GET_AREA_STATUS RESULT="102" CMD_RESULT="ERROR" />'
        "</FLEXML_REPLY>"
    )

    assert parse_area_status(response) == [
        {
            "AREA_ID": "1",
            "AREA_NAME": "Logis",
            "MODE": "0",
        },
        {
            "AREA_ID": "2",
            "AREA_NAME": "Garage",
            "MODE": "0",
        },
    ]


def test_parse_area_status_raises_on_real_error() -> None:
    """Do not hide real AREA_STATUS command errors."""
    response = (
        '<FLEXML_REPLY VER="1.0">'
        '<REPLY_GET_AREA_STATUS RESULT="54" CMD_RESULT="ERROR" />'
        "</FLEXML_REPLY>"
    )

    with pytest.raises(FlexMLReplyError):
        parse_area_status(response)
