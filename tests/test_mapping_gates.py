"""Tests for SPC Mapping Gate support."""

import pytest

from custom_components.spc_flexc.flexc.flexml import (
    FlexMLError,
    FlexMLReplyError,
    build_mg_control_command,
    build_mg_status_command,
    parse_mg_control,
    parse_mg_status,
)


def test_mg_discovery_uses_aggregate_id_zero() -> None:
    """Mapping Gate discovery must not scan a model-dependent ID range."""
    xml = build_mg_status_command("HomeAssistant", "MyPassword")
    assert '<CMD_GET_MG_STATUS MG_ID="0" />' in xml


def test_parse_mg_status_multiple_mapping_gates() -> None:
    """Aggregate status returns every configured Mapping Gate."""
    response = (
        '<FLEXML_REPLY VER="1.0">'
        '<REPLY_GET_MG_STATUS RESULT="0" CMD_RESULT="OK">'
        '<MG_STATUS MG_ID="1" MG_NAME="Test one" STATE="0" />'
        '<MG_STATUS MG_ID="4" MG_NAME="Test four" STATE="1" />'
        '</REPLY_GET_MG_STATUS></FLEXML_REPLY>'
    )
    assert parse_mg_status(response) == [
        {"MG_ID": "1", "MG_NAME": "Test one", "STATE": "0"},
        {"MG_ID": "4", "MG_NAME": "Test four", "STATE": "1"},
    ]


def test_parse_empty_mg_status() -> None:
    """Panels with no configured Mapping Gate return an empty successful reply."""
    response = (
        '<FLEXML_REPLY VER="1.0">'
        '<REPLY_GET_MG_STATUS RESULT="0" CMD_RESULT="OK">'
        '</REPLY_GET_MG_STATUS></FLEXML_REPLY>'
    )
    assert parse_mg_status(response) == []


def test_mg_control_uses_validated_numeric_actions() -> None:
    """Only the real-panel validated 0/1 actions may be emitted."""
    assert '<CMD_MG_CONTROL MG_ID="1" ACTION="1" />' in build_mg_control_command(
        1, 1, "HomeAssistant", "MyPassword"
    )
    assert '<CMD_MG_CONTROL MG_ID="1" ACTION="0" />' in build_mg_control_command(
        1, 0, "HomeAssistant", "MyPassword"
    )
    with pytest.raises(ValueError):
        build_mg_control_command(1, 2, "HomeAssistant", "MyPassword")


def test_parse_mg_control_real_panel_reply() -> None:
    """Accept the successful reply captured from a real SPC4300."""
    response = (
        '<FLEXML_REPLY VER="1.0">'
        '<REPLY_MG_CONTROL RESULT="0" CMD_RESULT="OK">'
        '<MG_CONTROL MG_ID="1" RESULT="0"/>'
        '</REPLY_MG_CONTROL></FLEXML_REPLY>'
    )
    parse_mg_control(response, 1)


def test_parse_mg_control_rejects_wrong_id() -> None:
    """A successful result for another Mapping Gate must not validate control."""
    response = (
        '<FLEXML_REPLY VER="1.0">'
        '<REPLY_MG_CONTROL RESULT="0" CMD_RESULT="OK">'
        '<MG_CONTROL MG_ID="2" RESULT="0"/>'
        '</REPLY_MG_CONTROL></FLEXML_REPLY>'
    )
    with pytest.raises(FlexMLError):
        parse_mg_control(response, 1)


def test_parse_mg_control_rejects_inner_error() -> None:
    """Reject a failed MG_CONTROL result."""
    response = (
        '<FLEXML_REPLY VER="1.0">'
        '<REPLY_MG_CONTROL RESULT="0" CMD_RESULT="OK">'
        '<MG_CONTROL MG_ID="1" RESULT="54"/>'
        '</REPLY_MG_CONTROL></FLEXML_REPLY>'
    )
    with pytest.raises(FlexMLReplyError):
        parse_mg_control(response, 1)
