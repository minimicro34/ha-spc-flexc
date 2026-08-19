from types import SimpleNamespace

import pytest
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelState,
)
from homeassistant.exceptions import ServiceValidationError

from custom_components.spc_flexc.alarm_control_panel import (
    MODE_LABELS,
    _active_blocking_faults,
    _raise_not_ready,
)
from custom_components.spc_flexc.models import (
    AreaState,
    FaultState,
)


def test_area_mode_labels() -> None:
    assert MODE_LABELS == {
        0: "Unset",
        1: "PartSetA",
        2: "PartSetB",
        3: "Set",
    }


def test_expected_home_assistant_mode_mapping() -> None:
    mapping = {
        0: AlarmControlPanelState.DISARMED,
        1: AlarmControlPanelState.ARMED_AWAY,
        2: AlarmControlPanelState.ARMED_HOME,
        3: AlarmControlPanelState.ARMED_NIGHT,
    }

    assert mapping[0] is AlarmControlPanelState.DISARMED
    assert mapping[1] is AlarmControlPanelState.ARMED_AWAY
    assert mapping[2] is AlarmControlPanelState.ARMED_HOME
    assert mapping[3] is AlarmControlPanelState.ARMED_NIGHT


def test_active_blocking_faults() -> None:
    """Test collection of known blocking panel faults."""
    coordinator = SimpleNamespace(
        data=SimpleNamespace(
            faults=FaultState(
                mains_fault=True,
                battery_fault=True,
                panel_tamper=True,
            )
        )
    )

    assert _active_blocking_faults(coordinator) == [
        "230 V mains fault",
        "panel battery fault",
        "panel tamper",
    ]


def test_reason_2007_with_active_faults() -> None:
    """Test generic SPC 2007 reason enriched with known active faults."""
    coordinator = SimpleNamespace(
        data=SimpleNamespace(
            faults=FaultState(
                mains_fault=True,
                panel_tamper=True,
            ),
            areas={
                2: AreaState(
                    area_id=2,
                    name="Garage",
                )
            },
            zones={},
        )
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        _raise_not_ready(
            coordinator,
            2,
            "2007",
        )

    error = exc_info.value

    assert error.translation_key == "area_not_ready_faults"
    assert error.translation_placeholders == {
        "area": "Garage",
        "reason": "2007",
        "faults": "230 V mains fault, panel tamper",
    }


def test_reason_2007_without_known_fault() -> None:
    """Test generic SPC 2007 reason without a known active cause."""
    coordinator = SimpleNamespace(
        data=SimpleNamespace(
            faults=FaultState(),
            areas={
                2: AreaState(
                    area_id=2,
                    name="Garage",
                )
            },
            zones={},
        )
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        _raise_not_ready(
            coordinator,
            2,
            "2007",
        )

    error = exc_info.value

    assert error.translation_key == "area_not_ready"
    assert error.translation_placeholders == {
        "area": "Garage",
        "reason": "2007",
    }
