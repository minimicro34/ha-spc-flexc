"""Tests for the SPC FlexC config flow."""

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.spc_flexc.const import (
    CONF_COMMAND_PASSWORD,
    CONF_COMMAND_USERNAME,
    CONF_KEY,
    CONF_PORT,
    DOMAIN,
)

OLD_DATA = {
    CONF_HOST: "192.168.1.200",
    CONF_PORT: 52000,
    CONF_KEY: "1" * 64,
    CONF_COMMAND_USERNAME: "homeassistant",
    CONF_COMMAND_PASSWORD: "old-password",
}

NEW_DATA = {
    CONF_HOST: "192.168.1.201",
    CONF_PORT: 52001,
    CONF_KEY: "2" * 64,
    CONF_COMMAND_USERNAME: "new-homeassistant",
    CONF_COMMAND_PASSWORD: "new-password",
}


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the initial user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        OLD_DATA,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "SPC 192.168.1.200"
    assert result["data"] == OLD_DATA
    assert result["result"].unique_id is None


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_duplicate_host_aborts(hass: HomeAssistant) -> None:
    """Test that an already configured SPC host is rejected."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SPC",
        data=OLD_DATA,
        unique_id="SPC12345678",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        OLD_DATA,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_reconfigure_flow(hass: HomeAssistant) -> None:
    """Test updating all SPC FlexC connection settings."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SPC",
        data=OLD_DATA,
        unique_id="SPC12345678",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        NEW_DATA,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == NEW_DATA
    assert entry.unique_id == "SPC12345678"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_reconfigure_duplicate_host_aborts(
    hass: HomeAssistant,
) -> None:
    """Test reconfiguration cannot reuse another SPC entry host."""
    first_entry = MockConfigEntry(
        domain=DOMAIN,
        title="SPC first",
        data=OLD_DATA,
        unique_id="SPC12345678",
    )
    first_entry.add_to_hass(hass)

    second_data = {
        **OLD_DATA,
        CONF_HOST: "192.168.1.250",
    }
    second_entry = MockConfigEntry(
        domain=DOMAIN,
        title="SPC second",
        data=second_data,
        unique_id="SPC87654321",
    )
    second_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": first_entry.entry_id,
        },
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            **NEW_DATA,
            CONF_HOST: "192.168.1.250",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert first_entry.data == OLD_DATA
    assert first_entry.unique_id == "SPC12345678"
