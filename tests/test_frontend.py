"""Tests for the bundled Lovelace card registration and migration."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.spc_flexc.frontend import async_register_card


@pytest.fixture
def hass() -> MagicMock:
    """Create a minimal Home Assistant frontend fixture."""
    instance = MagicMock()
    instance.data = {}
    instance.http.async_register_static_paths = AsyncMock()
    return instance


@pytest.mark.asyncio
async def test_register_card_once_with_multiple_panels(hass: MagicMock) -> None:
    """Register the HTTP path and resource only once for multiple entries."""
    resources = MagicMock()
    resources.loaded = True
    resources.async_items.return_value = []
    resources.async_create_item = AsyncMock()
    hass.data["lovelace"] = SimpleNamespace(
        resource_mode="storage", resources=resources
    )

    await async_register_card(hass)
    resources.async_items.return_value = [
        {
            "id": "card",
            "url": "/spc_flexc/ha-spc-flexc-card.js?v=1.0.18",
            "res_type": "module",
        }
    ]
    await async_register_card(hass)

    hass.http.async_register_static_paths.assert_awaited_once()
    resources.async_create_item.assert_awaited_once_with(
        {"url": "/spc_flexc/ha-spc-flexc-card.js?v=1.0.18", "res_type": "module"}
    )


@pytest.mark.asyncio
async def test_load_resources_before_migration(hass: MagicMock) -> None:
    """Load persisted resources before modifying the collection."""
    resources = MagicMock()
    resources.loaded = False
    resources.async_load = AsyncMock()
    resources.async_items.return_value = [
        {
            "id": "legacy",
            "url": "/hacsfiles/ha-spc-flexc-card/ha-spc-flexc-card.js",
            "res_type": "module",
        }
    ]
    resources.async_update_item = AsyncMock()
    resources.async_create_item = AsyncMock()
    hass.data["lovelace"] = SimpleNamespace(
        resource_mode="storage", resources=resources
    )

    await async_register_card(hass)

    resources.async_load.assert_awaited_once()
    resources.async_update_item.assert_awaited_once_with(
        "legacy",
        {"url": "/spc_flexc/ha-spc-flexc-card.js?v=1.0.18", "res_type": "module"},
    )
    resources.async_create_item.assert_not_awaited()


@pytest.mark.asyncio
async def test_yaml_resources_are_not_modified(hass: MagicMock) -> None:
    """YAML mode must not be modified through storage collection APIs."""
    resources = MagicMock()
    hass.data["lovelace"] = SimpleNamespace(resource_mode="yaml", resources=resources)

    await async_register_card(hass)

    hass.http.async_register_static_paths.assert_awaited_once()
    resources.async_create_item.assert_not_called()


@pytest.mark.asyncio
async def test_duplicate_legacy_resources_require_manual_cleanup(
    hass: MagicMock,
) -> None:
    """Avoid registering a third copy when two legacy resources exist."""
    resources = MagicMock()
    resources.loaded = True
    resources.async_items.return_value = [
        {"id": "one", "url": "/hacsfiles/ha-spc-flexc-card/ha-spc-flexc-card.js"},
        {"id": "two", "url": "/local/community/ha-spc-flexc-card/ha-spc-flexc-card.js"},
    ]
    resources.async_create_item = AsyncMock()
    resources.async_update_item = AsyncMock()
    hass.data["lovelace"] = SimpleNamespace(
        resource_mode="storage", resources=resources
    )

    await async_register_card(hass)

    resources.async_create_item.assert_not_awaited()
    resources.async_update_item.assert_not_awaited()
