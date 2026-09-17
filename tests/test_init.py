"""Tests for SPC FlexC integration setup and unload."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.spc_flexc import async_setup_entry, async_unload_entry
from custom_components.spc_flexc.const import PLATFORMS


@pytest.mark.asyncio
async def test_setup_entry_initializes_and_starts_discovery() -> None:
    """Setup performs the first refresh, forwards platforms and starts discovery."""
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    entry = MagicMock()
    entry.unique_id = None

    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.data.panel.serial_number = "SPC12345678"

    with patch(
        "custom_components.spc_flexc.SpcFlexCMappingGateCoordinator",
        return_value=coordinator,
    ):
        assert await async_setup_entry(hass, entry) is True

    coordinator.async_config_entry_first_refresh.assert_awaited_once_with()
    hass.config_entries.async_update_entry.assert_called_once_with(
        entry, unique_id="SPC12345678"
    )
    assert entry.runtime_data is coordinator
    hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(
        entry, PLATFORMS
    )
    coordinator.async_start_background_discovery.assert_called_once_with()


@pytest.mark.asyncio
async def test_setup_entry_keeps_existing_serial() -> None:
    """Setup does not rewrite an entry that already has the panel serial."""
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    entry = MagicMock()
    entry.unique_id = "SPC12345678"

    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.data.panel.serial_number = "SPC12345678"

    with patch(
        "custom_components.spc_flexc.SpcFlexCMappingGateCoordinator",
        return_value=coordinator,
    ):
        assert await async_setup_entry(hass, entry) is True

    hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("unload_ok", [True, False])
async def test_unload_entry_shutdown_only_after_success(unload_ok: bool) -> None:
    """Coordinator shutdown follows successful platform unload only."""
    hass = MagicMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=unload_ok)
    entry = MagicMock()
    entry.runtime_data.async_shutdown = AsyncMock()

    assert await async_unload_entry(hass, entry) is unload_ok

    hass.config_entries.async_unload_platforms.assert_awaited_once_with(
        entry, PLATFORMS
    )
    if unload_ok:
        entry.runtime_data.async_shutdown.assert_awaited_once_with()
    else:
        entry.runtime_data.async_shutdown.assert_not_awaited()
