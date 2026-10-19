"""Regression tests for beta24 arm/disarm history and partial modes."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
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
    with patch(
        "custom_components.spc_flexc.coordinator.dt_util.get_default_time_zone",
        return_value=ZoneInfo("Europe/Paris"),
    ):
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


def test_history_display_name_prefers_alias_without_mutating_raw_identity():
    coordinator = _history_coordinator()
    coordinator.entry.options["user_aliases"] = {"9995": "Home Assistant"}
    coordinator._user_names[1] = "Panel Nicolas"

    assert coordinator._apply_area_history_event(
        _event(3502, "21394016102026", "9995", "Utilis.Profil Co")
    )
    area = coordinator.state.areas[1]
    assert area.last_arm_user_name == "Utilis.Profil Co"
    assert area.last_arm_user_display_name == "Home Assistant"

    assert coordinator._apply_area_history_event(
        _event(3501, "21394916102026", "1", "Event Nicolas")
    )
    assert area.last_disarm_user_name == "Event Nicolas"
    assert area.last_disarm_user_display_name == "Panel Nicolas"

    # The saved data contains only the panel/event identity, never an alias.
    saved = coordinator._save_area_history()["1"]
    assert saved["last_arm_user_name"] == "Utilis.Profil Co"
    assert saved["last_disarm_user_name"] == "Event Nicolas"
    assert "last_arm_user_display_name" not in saved

    # Alias edits must take effect when the area is rebuilt.
    coordinator.entry.options["user_aliases"]["9995"] = "Automatisation"
    rebuilt = AreaState(area_id=1)
    coordinator._merge_area_history(rebuilt)
    assert rebuilt.last_arm_user_display_name == "Automatisation"
    assert rebuilt.last_arm_user_name == "Utilis.Profil Co"


@pytest.mark.asyncio
@pytest.mark.parametrize("lookup_failure", [None, "flexml", "value"])
async def test_discovery_resolves_known_users_without_exposing_private_data(
    lookup_failure, caplog
):
    """Discovery resolves restored identities, ignoring missing or invalid users."""
    import asyncio
    from unittest.mock import AsyncMock, patch

    from custom_components.spc_flexc.flexc.flexml import FlexMLError

    coordinator = _history_coordinator()
    coordinator._area_history = {
        1: {
            "last_arm_user_id": 1,
            "last_arm_user_name": "Event Nicolas",
            "last_disarm_user_id": 9995,
            "last_disarm_user_name": "Control Profile",
        }
    }
    coordinator._client_operation_lock = asyncio.Lock()
    coordinator.client = SimpleNamespace(
        async_ensure_connected=AsyncMock(),
        async_get_user_name=AsyncMock(return_value="Panel Nicolas"),
    )
    if lookup_failure == "flexml":
        coordinator.client.async_get_user_name.side_effect = FlexMLError("unavailable")
    elif lookup_failure == "value":
        coordinator.client.async_get_user_name.side_effect = ValueError("unavailable")
    coordinator._detected_ats_ids = set()
    coordinator._detected_area_ids = set()
    coordinator._detected_zone_ids = set()
    coordinator._detected_door_ids = set()
    coordinator._detected_xbus_serials = set()
    coordinator._discovery_task = None
    coordinator._schedule_zone_polling = MagicMock()
    coordinator._schedule_xbus_polling = MagicMock()
    coordinator.async_set_updated_data = MagicMock()

    with (
        patch("custom_components.spc_flexc.coordinator.ATS_IDS", ()),
        patch(
            "custom_components.spc_flexc.coordinator.async_discover_areas",
            new_callable=AsyncMock,
            return_value=[{"AREA_ID": "1", "AREA_NAME": "Home", "MODE": "0"}],
        ),
        patch(
            "custom_components.spc_flexc.coordinator.async_discover_zones",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "custom_components.spc_flexc.coordinator.async_discover_doors",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "custom_components.spc_flexc.coordinator.async_get_xbus_status",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        await coordinator._async_discover_panel_objects()

    assert coordinator.client.async_get_user_name.await_count == 2
    assert {
        call.args[0] for call in coordinator.client.async_get_user_name.await_args_list
    } == {1, 9995}
    area = coordinator.state.areas[1]
    assert area.last_arm_user_name == "Event Nicolas"
    assert area.last_arm_user_display_name == (
        "Panel Nicolas" if lookup_failure is None else "Event Nicolas"
    )
    assert "Panel Nicolas" not in caplog.text
    coordinator.async_set_updated_data.assert_called_once()
