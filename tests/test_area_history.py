"""Regression tests for beta24 arm/disarm history and partial modes."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from custom_components.spc_flexc.coordinator import SpcFlexCCoordinator
from custom_components.spc_flexc.flexc.events import apply_area_event
from custom_components.spc_flexc.models import AreaState, SpcState


@pytest.mark.parametrize(
    ("event_id", "expected_mode"),
    [(3501, 0), (3502, 1), (3503, 2), (3504, 3)],
)
def test_area_modes_cover_partial_and_full_set(event_id, expected_mode):
    area = AreaState(area_id=1)
    assert apply_area_event({1: area}, {"EV_ID": str(event_id), "AREA_ID": "1"})
    assert area.mode == expected_mode


def _history_coordinator():
    """Construct a minimal coordinator without opening an SPC connection."""
    coordinator = object.__new__(SpcFlexCCoordinator)
    coordinator.hass = SimpleNamespace(config=SimpleNamespace(time_zone="Europe/Paris"))
    coordinator.state = SpcState(areas={1: AreaState(area_id=1)})
    coordinator._area_history = {}
    coordinator._user_names = {}
    coordinator.entry = SimpleNamespace(options={})
    coordinator._area_history_store = MagicMock()
    return coordinator


def _event(event_id, timestamp, user_id="9995", user_name="Control Profile"):
    return {
        "EV_ID": str(event_id),
        "AREA_ID": "1",
        "TIMESTAMP": timestamp,
        "USER_ID": user_id,
        "USER_NAME": user_name,
    }


def test_history_tracks_partial_arm_and_disarm_without_overwriting_full_set_fields():
    coordinator = _history_coordinator()
    area = coordinator.state.areas[1]
    assert coordinator._apply_area_history_event(_event(3502, "21394016102026"))
    assert area.last_arm_user_id == 9995
    assert area.last_arm_user_name == "Control Profile"
    assert area.last_arm_time == datetime(
        2026, 10, 16, 21, 39, 40, tzinfo=ZoneInfo("Europe/Paris")
    )
    assert area.last_set_time is None

    assert coordinator._apply_area_history_event(
        _event(3501, "21394916102026", "1", "Nicolas")
    )
    assert area.last_disarm_user_id == 1
    assert area.last_disarm_user_name == "Nicolas"
    assert area.last_arm_user_id == 9995
    assert area.last_unset_time is None


def test_history_rejects_duplicate_out_of_order_and_invalid_timestamp():
    coordinator = _history_coordinator()
    assert coordinator._apply_area_history_event(_event(3504, "22000016102026"))
    assert not coordinator._apply_area_history_event(_event(3501, "21595916102026"))
    assert not coordinator._apply_area_history_event(_event(3504, "22000016102026"))
    assert not coordinator._apply_area_history_event(_event(3503, "invalid"))
    assert coordinator.state.areas[1].last_disarm_time is None
    assert coordinator._area_history_store.async_delay_save.call_count == 1


def test_history_survives_area_rebuild_and_serialization():
    coordinator = _history_coordinator()
    assert coordinator._apply_area_history_event(_event(3503, "22100016102026"))
    replacement = AreaState(area_id=1, mode=2)
    coordinator._merge_area_history(replacement)
    assert replacement.last_arm_user_id == 9995
    assert replacement.last_arm_time == coordinator.state.areas[1].last_arm_time
    saved = coordinator._save_area_history()
    assert saved["1"]["last_arm_user_id"] == 9995
    assert saved["1"]["last_arm_time"].startswith("2026-10-16T22:10:00")


@pytest.mark.asyncio
async def test_history_restore_keeps_only_valid_aware_timestamps():
    coordinator = _history_coordinator()
    coordinator._area_history_store.async_load.return_value = {
        "1": {
            "last_arm_time": "2026-10-16T21:39:40+02:00",
            "last_arm_user_id": 9995,
            "last_arm_user_name": "Control Profile",
            "last_disarm_time": "invalid",
        },
        "2": {"last_arm_time": "2026-10-16T21:39:40"},
    }
    # async_load must be awaitable.
    from unittest.mock import AsyncMock

    coordinator._area_history_store.async_load = AsyncMock(
        return_value=coordinator._area_history_store.async_load.return_value
    )
    await coordinator.async_restore_area_history()
    assert coordinator._area_history[1]["last_arm_user_id"] == 9995
    assert (
        coordinator._area_history[1]["last_arm_user_display_name"] == "Control Profile"
    )
    assert 2 not in coordinator._area_history
