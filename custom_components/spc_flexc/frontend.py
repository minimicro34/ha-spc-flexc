"""Register the bundled SPC FlexC dashboard card safely."""

import asyncio
import logging
from pathlib import Path
from urllib.parse import urlsplit

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
_CARD_PATH = "/spc_flexc/ha-spc-flexc-card.js"
_CARD_VERSION = "1.0.20"
_CARD_URL = f"{_CARD_PATH}?v={_CARD_VERSION}"
_LEGACY_PATHS = {
    "/hacsfiles/ha-spc-flexc-card/ha-spc-flexc-card.js",
    "/local/community/ha-spc-flexc-card/ha-spc-flexc-card.js",
}
_LOCK_KEY = "spc_flexc_frontend_lock"
_PATH_KEY = "spc_flexc_frontend_path_registered"


async def async_register_card(hass: HomeAssistant) -> None:
    """Expose and register the bundled card, once per Home Assistant instance."""
    async with hass.data.setdefault(_LOCK_KEY, asyncio.Lock()):
        if not hass.data.get(_PATH_KEY):
            await hass.http.async_register_static_paths(
                [
                    StaticPathConfig(
                        _CARD_PATH,
                        str(Path(__file__).parent / "www" / "ha-spc-flexc-card.js"),
                        False,
                    )
                ]
            )
            hass.data[_PATH_KEY] = True

        lovelace = hass.data.get("lovelace")
        if lovelace is None:
            _LOGGER.warning(
                "Lovelace is not loaded; add %s as a JavaScript module manually",
                _CARD_URL,
            )
            return
        if lovelace.resource_mode != "storage":
            _LOGGER.info(
                "Lovelace resources use YAML; add %s as a module resource",
                _CARD_URL,
            )
            return

        resources = lovelace.resources
        # Load the collection before any read or mutation. Otherwise early
        # async_create_item calls can overwrite existing Lovelace resources.
        if not resources.loaded:
            await resources.async_load()

        existing = resources.async_items()
        bundled = [
            item for item in existing if urlsplit(item["url"]).path == _CARD_PATH
        ]
        legacy = [
            item for item in existing if urlsplit(item["url"]).path in _LEGACY_PATHS
        ]

        if bundled:
            for item in bundled:
                if item["url"] != _CARD_URL or item.get("res_type") != "module":
                    await resources.async_update_item(
                        item["id"], {"url": _CARD_URL, "res_type": "module"}
                    )
            if legacy:
                _LOGGER.warning(
                    "Legacy SPC FlexC Card resources remain installed; "
                    "remove the standalone HACS card and duplicate resources"
                )
            return

        if len(legacy) == 1:
            await resources.async_update_item(
                legacy[0]["id"], {"url": _CARD_URL, "res_type": "module"}
            )
            _LOGGER.info("Migrated standalone SPC FlexC Card Lovelace resource")
            return
        if len(legacy) > 1:
            _LOGGER.warning(
                "Multiple legacy SPC FlexC Card resources found; remove duplicates "
                "before registering %s",
                _CARD_URL,
            )
            return

        await resources.async_create_item({"url": _CARD_URL, "res_type": "module"})
        _LOGGER.info("Registered bundled SPC FlexC Card %s", _CARD_URL)
