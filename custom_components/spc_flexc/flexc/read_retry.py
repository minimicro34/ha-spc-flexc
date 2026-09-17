"""Bounded retry helpers for read-only FlexC operations."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from .connection import FlexCConnectionError

_LOGGER = logging.getLogger(__name__)
_T = TypeVar("_T")


async def async_retry_read_once(
    operation: Callable[[], Awaitable[_T]],
    *,
    description: str,
) -> _T:
    """Retry one read-only FlexC operation once after a connection loss."""
    try:
        return await operation()
    except FlexCConnectionError as err:
        _LOGGER.info(
            "FlexC read interrupted while %s; retrying once after reconnect: %s",
            description,
            err,
        )
        return await operation()
