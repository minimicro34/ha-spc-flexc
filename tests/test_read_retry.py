"""Tests for bounded read-only FlexC retries."""

from unittest.mock import AsyncMock

import pytest

from custom_components.spc_flexc.flexc.connection import (
    FlexCCommandError,
    FlexCConnectionError,
)
from custom_components.spc_flexc.flexc.read_retry import async_retry_read_once


@pytest.mark.asyncio
async def test_read_retries_once_after_connection_loss() -> None:
    """A read interrupted by a connection loss is replayed once."""
    operation = AsyncMock(
        side_effect=[
            FlexCConnectionError("connection closed"),
            {"ok": True},
        ]
    )

    result = await async_retry_read_once(operation, description="testing read")

    assert result == {"ok": True}
    assert operation.await_count == 2


@pytest.mark.asyncio
async def test_read_does_not_retry_command_error() -> None:
    """Protocol/command rejection is not treated as a reconnectable read loss."""
    operation = AsyncMock(side_effect=FlexCCommandError("rejected"))

    with pytest.raises(FlexCCommandError, match="rejected"):
        await async_retry_read_once(operation, description="testing read")

    operation.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_read_never_retries_more_than_once() -> None:
    """A second connection loss is propagated instead of looping forever."""
    operation = AsyncMock(
        side_effect=[
            FlexCConnectionError("first loss"),
            FlexCConnectionError("second loss"),
        ]
    )

    with pytest.raises(FlexCConnectionError, match="second loss"):
        await async_retry_read_once(operation, description="testing read")

    assert operation.await_count == 2
