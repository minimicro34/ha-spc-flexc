"""Tests for FLEXML command generation."""

from custom_components.spc_flexc.flexc.flexml import (
    build_area_status_batch,
    build_panel_summary_command,
    build_zone_status_batch,
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
