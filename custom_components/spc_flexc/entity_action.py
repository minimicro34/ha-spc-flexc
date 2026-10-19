"""Translate SPC command failures into Home Assistant service errors."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import TypeVar

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .flexc.connection import FlexCError
from .flexc.flexml import FlexMLError

_T = TypeVar("_T")


async def async_entity_action(action: Awaitable[_T]) -> _T:
    """Run an entity action and expose expected failures to the UI."""
    try:
        return await action
    except HomeAssistantError:
        raise
    except ValueError as err:
        raise ServiceValidationError(str(err)) from err
    except (FlexCError, FlexMLError) as err:
        raise HomeAssistantError("SPC communication failed") from err
